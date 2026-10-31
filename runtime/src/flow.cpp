#include "runtime.hpp"
#include <regex>

namespace rt {
std::size_t DispatchSwitch(const Value& value,const Json& cases) {
    return std::visit([&](const auto& item)->std::size_t {
        using T=std::decay_t<decltype(item)>;
        if constexpr(std::is_same_v<T,std::int64_t> || std::is_same_v<T,std::string>)
            return SwitchBranch(item,FromJson<Array<T>>(cases));
        else throw std::runtime_error("Switch requires an integer or string");
    },value);
}
namespace {
void check(bool valid,const char* message) { if(!valid) throw std::runtime_error(message); }
void node_id(const std::string& node) {
    static const std::regex pattern("([0-9]{1,10}/)?[A-Za-z0-9_-]{1,128}");
    check(std::regex_match(node,pattern),"Invalid flow node identity");
}
FlowState& state(Ctx& c,const std::string& node,int type,EntityRef owner,bool initial=false) {
    check(c.flow_nodes.contains(node) && c.flow_nodes.at(node)==type,"Flow node is not registered in this program");
    if(!owner.id.empty()) NativeEntity(c,owner.id);
    auto key=std::pair{owner.id,node}; auto found=c.flow_states.find(key);
    if(found!=c.flow_states.end()) return found->second;
    check(c.flow_states.size()<4096,"At most 4096 flow states are allowed");
    return c.flow_states.emplace(std::move(key),FlowState{0,initial}).first->second;
}
}
void ConfigureFlow(Ctx& c,const Json& program) {
    std::map<std::string,int> nodes;
    std::function<void(const Json&,int)> visit=[&](const Json& value,int depth) {
        check(depth<=1024,"Flow program nesting exceeds 1024");
        if(value.is_object() && value.value("op",Json())=="flow") {
            const auto node=FromJson<std::string>(value.at("node")); node_id(node);
            const auto type=FromJson<std::int64_t>(value.at("type"));
            check(type>=2007 && type<=2011,"Unknown flow node type");
            auto [it,inserted]=nodes.emplace(node,static_cast<int>(type));
            check(inserted || it->second==type,"Inconsistent flow node binding");
            check(nodes.size()<=65536,"Too many flow node definitions");
        }
        if(value.is_array()) for(const auto& child:value) visit(child,depth+1);
        // Only execution blocks contain flow nodes. Literal maps and function
        // defaults can have arbitrary keys, including "op" and "type".
        else if(value.is_object()) for(const auto key:{"body","yes","no","branches"})
            if(value.contains(key)) visit(value.at(key),depth+1);
    };
    for(const auto& block:program.at("events")) visit(block,0);
    for(const auto& function:program.value("functions",Json::object())) visit(function.at("body"),0);
    if(program.contains("continuations")) visit(program.at("continuations").at("instructions"),0);
    c.flow_nodes=std::move(nodes); c.flow_states.clear();
}
FlowResult DoOnceFlow(Ctx& c,const std::string& node,const std::string& input,EntityRef owner) {
    check(input=="In" || input=="Reset","Invalid Do Once input");
    auto& s=state(c,node,2007,std::move(owner));
    if(input=="Reset") { s.count=0; return {}; }
    if(s.count) return {};
    s.count=1; return {0,1,false};
}
FlowResult DoNFlow(Ctx& c,const std::string& node,const std::string& input,EntityRef owner,std::int64_t limit) {
    check(input=="In" || input=="Reset","Invalid Do N input");
    check(input=="Reset" || limit>=0,"Do N limit must be nonnegative");
    auto& s=state(c,node,2008,std::move(owner));
    if(input=="Reset") { s.count=0; return {}; }
    if(s.count>=limit) return {-1,s.count,false};
    return {0,++s.count,false};
}
FlowResult GateFlow(Ctx& c,const std::string& node,const std::string& input,EntityRef owner,bool start_closed) {
    check(input=="In" || input=="Open" || input=="Close" || input=="Toggle","Invalid Gate input");
    auto& s=state(c,node,2009,std::move(owner),!start_closed);
    if(input=="Open") s.flag=true;
    else if(input=="Close") s.flag=false;
    else if(input=="Toggle") s.flag=!s.flag;
    return {input=="In" && s.flag ? 0 : -1,0,false};
}
FlowResult FlipFlopFlow(Ctx& c,const std::string& node,const std::string& input,EntityRef owner) {
    check(input=="In" || input=="Reset","Invalid Flip Flop input");
    auto& s=state(c,node,2010,std::move(owner),true);
    if(input=="Reset") { s.flag=true; return {}; }
    const bool is_a=s.flag; s.flag=!s.flag;
    return {is_a ? 0 : 1,0,is_a};
}
FlowResult MultiGateFlow(Ctx& c,const std::string& node,const std::string& input,EntityRef owner,
                        std::int64_t branches,bool random,bool loop,std::int64_t start) {
    check(input=="In" || input=="Reset","Invalid Multi Gate input");
    // shortcut: eight visible routes; extend the registry/layout together if
    // projects need more routes on one node.
    check(input=="Reset" || (branches>=1 && branches<=8),"Multi Gate Branches must be between 1 and 8");
    check(input=="Reset" || (start>=-1 && start<branches),"Multi Gate Start Index must be -1 or a valid branch index");
    auto& s=state(c,node,2011,std::move(owner));
    if(input=="Reset") { s={}; return {}; }
    auto next=s;
    if(next.branches!=branches) { next={}; next.branches=static_cast<int>(branches); }
    const int all=(1<<next.branches)-1;
    if(next.used==all) {
        if(!loop) return {};
        next.used=0; next.next=0;
    }
    int selected=-1;
    if(!next.used && start>=0) selected=static_cast<int>(start);
    else if(random) {
        std::vector<int> available;
        for(int i=0;i<next.branches;++i) if(!(next.used&(1<<i))) available.push_back(i);
        selected=available.at(static_cast<size_t>(RandomInteger(c,0,static_cast<int64_t>(available.size())-1)));
    } else {
        for(int i=0;i<next.branches;++i) {
            const int candidate=(next.next+i)%next.branches;
            if(!(next.used&(1<<candidate))) { selected=candidate; break; }
        }
    }
    next.used|=1<<selected; next.next=(selected+1)%next.branches; s=next;
    return {selected,0,false,selected};
}
FlowResult DispatchFlow(Ctx& c,int type,const std::string& node,const std::string& input,const std::vector<Value>& args) {
    const size_t count=type==2011 && input=="In" ? 5 : type==2009 || (type==2008 && input=="In") ? 2 : 1;
    check(args.size()==count,"Flow input argument count mismatch");
    const auto owner=std::get<EntityRef>(args.at(0));
    if(type==2007) return DoOnceFlow(c,node,input,owner);
    if(type==2008) return DoNFlow(c,node,input,owner,input=="In" ? std::get<int64_t>(args.at(1)) : 0);
    if(type==2009) return GateFlow(c,node,input,owner,std::get<bool>(args.at(1)));
    if(type==2010) return FlipFlopFlow(c,node,input,owner);
    if(type==2011) return input=="Reset" ? MultiGateFlow(c,node,input,owner) :
        MultiGateFlow(c,node,input,owner,std::get<int64_t>(args.at(1)),std::get<bool>(args.at(2)),std::get<bool>(args.at(3)),std::get<int64_t>(args.at(4)));
    throw std::runtime_error("Unknown flow node type");
}
void ForgetEntityFlow(Ctx& c,const std::string& owner) {
    std::erase_if(c.flow_states,[&](const auto& item){return item.first.first==owner;});
}
Json FlowCheckpoint(const Ctx& c) {
    Json states=Json::array();
    for(const auto& [key,state]:c.flow_states) {
        Json entry={{"owner",key.first},{"node",key.second},{"count",state.count},{"flag",state.flag}};
        if(c.flow_nodes.at(key.second)==2011) entry["multi"]={{"branches",state.branches},{"used",state.used},{"next",state.next}};
        states.push_back(std::move(entry));
    }
    return {{"version",1},{"bindings",c.flow_nodes},{"states",states}};
}
void RestoreFlow(Ctx& c,const Json& saved) {
    check(saved.is_object() && saved.size()==3 && saved.at("version").is_number_integer() && saved.at("version")==1 &&
        saved.at("bindings")==Json(c.flow_nodes),"Invalid or incompatible flow checkpoint");
    const auto& states=saved.at("states"); check(states.is_array() && states.size()<=4096,"Invalid flow state collection");
    decltype(c.flow_states) next;
    for(const auto& entry:states) {
        check(entry.is_object(),"Invalid saved flow state fields");
        const auto node=FromJson<std::string>(entry.at("node"));
        const auto owner=FromJson<EntityRef>(entry.at("owner"));
        check(c.flow_nodes.contains(node),"Unknown saved flow node");
        if(!owner.id.empty()) NativeEntity(c,owner.id);
        const auto count=FromJson<int64_t>(entry.at("count")); const auto flag=FromJson<bool>(entry.at("flag"));
        const auto type=c.flow_nodes.at(node);
        check(entry.size()==(type==2011 ? 5u : 4u),"Invalid saved flow state fields");
        check(count>=0 && (type==2008 || count<=(type==2007 ? 1 : 0)) && ((type==2009 || type==2010) || !flag),"Invalid saved flow node state");
        FlowState state{count,flag};
        if(type==2011) {
            const auto& multi=entry.at("multi");
            check(multi.is_object() && multi.size()==3,"Invalid saved Multi Gate fields");
            const auto branches=FromJson<int64_t>(multi.at("branches")),used=FromJson<int64_t>(multi.at("used")),cursor=FromJson<int64_t>(multi.at("next"));
            check(branches>=0 && branches<=8 && used>=0 && used<(1<<branches) && cursor>=0 && cursor<std::max<int64_t>(branches,1),"Invalid saved Multi Gate state");
            check((branches==0)==(used==0),"Invalid saved Multi Gate progress");
            check((used==0 && cursor==0) || (used&(1<<((cursor+branches-1)%branches))),"Invalid saved Multi Gate cursor");
            state.branches=static_cast<int>(branches); state.used=static_cast<int>(used); state.next=static_cast<int>(cursor);
        }
        check(next.emplace(std::pair{owner.id,node},state).second,"Duplicate saved flow state");
    }
    c.flow_states=std::move(next);
}
}
