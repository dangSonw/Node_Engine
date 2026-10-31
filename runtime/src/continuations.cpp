#include "node_code.hpp"
#include "../third_party/picosha2/picosha2.hpp"

namespace rt {
namespace {
constexpr std::size_t MaxTasks=256, MaxFrames=128, MaxSegments=1024, MaxBytes=32*1024*1024;
void check(bool ok,const char* message) { if(!ok) throw std::runtime_error(message); }
struct Segment {
    std::string kind="block";
    std::size_t ref=0, pc=0, count=0;
    Value items=Array<double>{};
};
struct Frame {
    int function=0;
    std::vector<Value> parameters;
    CapturedValues locals;
    std::vector<Segment> stack;
};
struct Task {
    int64_t id=0;
    std::size_t entry=0, wait=0;
    std::string self,owner;
    double remaining=0;
    bool unscaled=false;
    std::vector<Frame> frames;
};
struct Program {
    Json data;
    std::string hash;
    ContinuationEval eval;
    ContinuationAction action;
};
struct Context {
    Ctx& c; Frame& frame;
    std::string self;
    int depth;
    Context(Ctx& c,Frame& frame,const Task& task):c(c),frame(frame),self(c.self),depth(c.call_depth) {
        check(depth+task.frames.size()<=MaxFrames,"Function call depth exceeds 128");
        c.locals.swap(frame.locals); c.parameters.swap(frame.parameters);
        c.self=task.self; c.call_depth=depth+static_cast<int>(task.frames.size())-1;
    }
    ~Context() { c.locals.swap(frame.locals); c.parameters.swap(frame.parameters); c.self=std::move(self); c.call_depth=depth; }
};
std::pair<std::string,std::string> key(const Json& p) { return {p.at("node").get<std::string>(),p.at("port").get<std::string>()}; }
std::string type(const Value& v) { return ValueType(v); }
Json packed(const Value& v) {
    return std::visit([&](const auto& item)->Json { return {{"type",ValueType(v)},{"value",ToJson(item)}}; },v);
}
Value unpacked(const Ctx& c,const Json& j) {
    check(j.is_object() && j.size()==2,"Invalid captured value");
    return CheckedValueFromJson(c,j.at("type").get<std::string>(),j.at("value"));
}
std::size_t index(const Json& j) {
    const auto n=FromJson<int64_t>(j); check(n>=0,"Negative continuation index"); return static_cast<std::size_t>(n);
}
void capture_scope(CapturedValues& values,const Json& schema,bool exact=false) {
    std::set<std::pair<std::string,std::string>> keys;
    for(const auto& p:schema) {
        const auto k=key(p); keys.insert(k);
        check(values.contains(k) && type(values.at(k))==p.at("type").get<std::string>(),"Missing or mistyped continuation local");
    }
    if(exact) check(values.size()==keys.size(),"Unexpected continuation local");
    else std::erase_if(values,[&](const auto& v){return !keys.contains(v.first);});
}
void parameters(const Ctx& c,const std::vector<Value>& values,const Json& schema) {
    check(values.size()==schema.size(),"Continuation function argument count mismatch");
    for(std::size_t i=0;i<values.size();++i) ValidateTypedValue(c,schema.at(i).at("type").get<std::string>(),values[i]);
}
}
struct Continuations {
    std::shared_ptr<const Program> program;
    std::map<int64_t,Task> pending;
    int64_t next=1;
    bool running=false;
};
namespace {
const Json& instruction(const Continuations& system,std::size_t id) { return system.program->data.at("instructions").at(id); }
const Json& block(const Continuations& system,std::size_t id) { return system.program->data.at("blocks").at(id); }
Frame frame(int function,std::size_t body,std::vector<Value> args={},CapturedValues locals={}) {
    return {function,std::move(args),std::move(locals),{{"block",body}}};
}
void push(Frame& f,Segment s) {
    check(f.stack.size()<MaxSegments,"Continuation stack exceeds 1024 segments"); f.stack.push_back(std::move(s));
}
Value evaluate(Ctx& c,Continuations& system,Task& task,std::size_t iid,std::size_t arg) {
    Context context(c,task.frames.back(),task);
    if(system.program->eval) return system.program->eval(c,iid,arg);
    return Evaluate(c,instruction(system,iid).at("args").at(arg));
}
void outputs(Frame& f,const Json& s,std::vector<Value> values) {
    check(s.at("outputs").size()==values.size(),"Continuation result count mismatch");
    const auto node=s.at("node").get<std::string>();
    for(std::size_t i=0;i<values.size();++i) f.locals[{node,s.at("outputs").at(i).get<std::string>()}]=std::move(values[i]);
}
Json task_json(const Task& task);
void run(Ctx& c,Continuations& system,Task task) {
    check(!system.running || DispatchingEntityDestroyed(c),"Continuation execution is already in progress");
    struct Guard { bool& value; bool previous; ~Guard(){value=previous;} } guard{system.running,system.running}; system.running=true;
    ExecutionScope execution(c);
    while(!task.frames.empty()) {
        if(!task.owner.empty() && !EntityExists(c,{task.owner})) return;
        auto& f=task.frames.back();
        if(f.stack.empty()) {
            check(f.function==0,"Function did not return its declared results"); return;
        }
        auto& segment=f.stack.back();
        if(segment.kind!="block") {
            const auto& s=instruction(system,segment.ref); const auto node=s.at("node").get<std::string>();
            if(segment.kind=="branch" || segment.kind=="flow" || segment.kind=="switch") { f.stack.pop_back(); continue; }
            bool again=false;
            if(segment.kind=="while") again=std::get<bool>(evaluate(c,system,task,segment.ref,0));
            else again=segment.pc<segment.count;
            Tick(c,node);
            if(!again) { f.stack.pop_back(); continue; }
            if(segment.kind=="foreach") {
                // Array contents are captured once, not re-read after a suspension.
                f.locals[{node,"Item"}]=std::visit([&](const auto& items)->Value {
                    using T=std::decay_t<decltype(items)>;
                    if constexpr(std::is_same_v<T,UserCollectionValue>) {
                        const auto element=items.type.substr(items.type.find('<')+1,items.type.size()-items.type.find('<')-2);
                        if(items.items.is_array()) return ValueFromJson(element,items.items.at(segment.pc));
                        auto it=items.items.begin(); std::advance(it,segment.pc); return ValueFromJson(element,it.value());
                    }
                    else if constexpr(ArrayType<T>::value) return typename T::value_type(items.at(segment.pc));
                    else if constexpr(SetType<T>::value) return typename T::value_type(items.values.at(segment.pc));
                    else if constexpr(MapType<T>::value) return MapValueAt(items,static_cast<std::int64_t>(segment.pc));
                    else throw std::runtime_error("For Each requires an array, set or map");
                },segment.items);
                std::visit([&](const auto& items) {
                    using T=std::decay_t<decltype(items)>;
                    if constexpr(std::is_same_v<T,UserCollectionValue>) {
                        if(items.items.is_object()) { auto it=items.items.begin(); std::advance(it,segment.pc); f.locals[{node,"Key"}]=it.key(); }
                    } else if constexpr(MapType<T>::value)
                        f.locals[{node,"Key"}]=MapKeyAt(items,static_cast<std::int64_t>(segment.pc));
                },segment.items);
                f.locals[{node,"Index"}]=static_cast<int64_t>(segment.pc);
            }
            if(segment.kind!="while") ++segment.pc;
            push(f,{"block",index(s.at("body"))}); continue;
        }
        const auto& code=block(system,segment.ref);
        if(segment.pc==code.size()) { f.stack.pop_back(); continue; }
        const auto iid=index(code.at(segment.pc)); const auto& s=instruction(system,iid);
        const auto op=s.at("op").get<std::string>(),node=s.at("node").get<std::string>();
        capture_scope(f.locals,s.at("locals"));
        if(op=="latent") {
            const auto owner=std::get<EntityRef>(evaluate(c,system,task,iid,0));
            Tick(c,node);
            if(!owner.id.empty()) NativeEntity(c,owner.id);
            auto duplicate=std::find_if(system.pending.begin(),system.pending.end(),[&](const auto& pending){
                return pending.second.owner==owner.id && instruction(system,pending.second.wait).at("node")==node;
            });
            if(duplicate!=system.pending.end() && s.at("type")!=2014) return;
            if(s.at("type")==2013 && std::get<bool>(evaluate(c,system,task,iid,1))) { ++segment.pc; continue; }
            double seconds=0; bool unscaled=false;
            if(s.at("type")!=2013) {
                seconds=std::get<double>(evaluate(c,system,task,iid,1));
                unscaled=std::get<bool>(evaluate(c,system,task,iid,2));
                check(std::isfinite(seconds) && seconds>=0,"Delay Seconds must be finite and nonnegative");
            }
            check(system.pending.size()<MaxTasks || duplicate!=system.pending.end(),"At most 256 pending continuations are allowed");
            check(system.next<INT64_MAX,"Continuation serial exhausted");
            // Every suspension receives a new serial, including a resumed loop.
            task.id=system.next; task.wait=iid; task.owner=owner.id;
            task.remaining=seconds; task.unscaled=unscaled;
            auto bytes=task_json(task).dump().size();
            for(auto it=system.pending.begin();it!=system.pending.end();++it)
                if(it!=duplicate) bytes+=task_json(it->second).dump().size();
            check(bytes<=MaxBytes-1024,"Pending continuations exceed 32 MiB");
            if(duplicate!=system.pending.end()) system.pending.erase(duplicate);
            ++system.next;
            system.pending.emplace(task.id,std::move(task)); return;
        }
        if(op=="while") { ++segment.pc; push(f,{"while",iid}); continue; }
        std::vector<Value> args;
        for(std::size_t i=0;i<s.at("args").size();++i) args.push_back(evaluate(c,system,task,iid,i));
        Tick(c,node); ++segment.pc;
        if(op=="return") {
            const auto fid=f.function;
            check(fid!=0,"Unexpected continuation return");
            parameters(c,args,system.program->data.at("functions").at(std::to_string(fid)).at("outputs"));
            task.frames.pop_back(); check(!task.frames.empty(),"Missing function caller");
            auto& caller=task.frames.back(); const auto& location=caller.stack.back();
            outputs(caller,instruction(system,index(block(system,location.ref).at(location.pc-1))),std::move(args));
        } else if(op=="function_call") {
            const auto fid=s.at("type").get<int>(); const auto& fn=system.program->data.at("functions").at(std::to_string(fid));
            parameters(c,args,fn.at("inputs"));
            check(task.frames.size()<MaxFrames,"Function call depth exceeds 128");
            task.frames.push_back(frame(fid,index(fn.at("body")),std::move(args)));
        } else if(op=="break" || op=="continue") {
            while(!f.stack.empty() && f.stack.back().kind!="for" && f.stack.back().kind!="foreach" && f.stack.back().kind!="while") f.stack.pop_back();
            check(!f.stack.empty(),"Loop control requires a loop Body in this graph");
            if(op=="break") f.stack.pop_back();
        } else if(op=="switch") {
            check(args.size()==1 && s.at("branches").size()==s.at("cases").size()+1,"Invalid Switch branches");
            const auto chosen=DispatchSwitch(args.at(0),s.at("cases"));
            push(f,{"switch",iid,chosen}); push(f,{"block",index(s.at("branches").at(chosen))});
        } else if(op=="branch") {
            const auto chosen=std::get<bool>(args.at(0)) ? 0u : 1u;
            push(f,{"branch",iid,chosen}); push(f,{"block",index(s.at(chosen ? "no" : "yes"))});
        } else if(op=="for") push(f,{"for",iid,0,static_cast<std::size_t>(LoopCount(std::get<double>(args.at(0))))});
        else if(op=="foreach") {
            const auto size=IterationValues(args.at(0)).size();
            push(f,{"foreach",iid,0,size,std::move(args.at(0))});
        } else if(op=="flow") {
            FlowResult result;
            { Context context(c,f,task); result=DispatchFlow(c,s.at("type").get<int>(),node,s.at("input").get<std::string>(),args); }
            if(result.branch>=0) {
                if(s.at("type")==2008) f.locals[{node,"Counter"}]=result.count;
                if(s.at("type")==2010) f.locals[{node,"Is A"}]=result.is_a;
                if(s.at("type")==2011) f.locals[{node,"Index"}]=result.index;
                push(f,{"flow",iid,static_cast<std::size_t>(result.branch)});
                push(f,{"block",index(s.at("branches").at(result.branch))});
            }
        } else {
            std::vector<Value> result;
            { Context context(c,f,task);
                if(op=="action" || op=="action_result") {
                    if(system.program->action) result=system.program->action(c,iid,args);
                    else if(!s.value("code",std::string{}).empty())
                        result=RunNodeCode(c,s.at("type").get<int>(),node,s.at("code").get<std::string>(),args);
                    else if(op=="action_result") result=dispatch_results(c,s.at("type").get<int>(),args);
                    else dispatch(c,s.at("type").get<int>(),args);
                } else if(op=="emit_event") SendEvent(c,s.at("event").get<int>(),std::get<EntityRef>(args.at(0)),std::get<EntityRef>(args.at(1)),std::vector<Value>(args.begin()+2,args.end()));
                else if(op=="broadcast_event") BroadcastEvent(c,s.at("event").get<int>(),std::get<EntityRef>(args.at(0)),std::vector<Value>(args.begin()+1,args.end()));
                else if(op=="subscribe_event" || op=="unsubscribe_event") SetEventSubscription(c,s.at("event").get<int>(),std::get<EntityRef>(args.at(0)),op=="subscribe_event");
                else throw std::runtime_error("Unknown continuation statement: "+op);
            }
            if(op=="action_result") outputs(f,s,std::move(result));
        }
    }
}
Json task_json(const Task& task) {
    auto frames=Json::array();
    for(const auto& f:task.frames) {
        auto args=Json::array(),locals=Json::array(),stack=Json::array();
        for(const auto& arg:f.parameters) args.push_back(packed(arg));
        for(const auto& [k,v]:f.locals) locals.push_back({{"node",k.first},{"port",k.second},{"value",packed(v)}});
        for(const auto& s:f.stack) stack.push_back({{"kind",s.kind},{"ref",s.ref},{"pc",s.pc},{"count",s.count},{"items",packed(s.items)}});
        frames.push_back({{"function",f.function},{"parameters",args},{"locals",locals},{"stack",stack}});
    }
    return {{"id",task.id},{"entry",task.entry},{"wait",task.wait},{"self",task.self},{"owner",task.owner},
            {"remaining",task.remaining},{"unscaled",task.unscaled},{"frames",frames}};
}
}
void ConfigureContinuations(Ctx& c,const Json& program,ContinuationEval eval,ContinuationAction action) {
    c.continuations.reset();
    if(!program.contains("continuations")) return;
    auto p=std::make_shared<Program>(); p->data=program.at("continuations");
    check(p->data.dump().size()<=MaxBytes,"Continuation program exceeds 32 MiB");
    p->hash=picosha2::hash256_hex_string(p->data.dump()); p->eval=std::move(eval); p->action=std::move(action);
    auto system=std::make_shared<Continuations>(); system->program=std::move(p); c.continuations=std::move(system);
}
void StartContinuation(Ctx& c,std::size_t entry,CapturedValues captures) {
    check(bool(c.continuations),"Continuations have not been configured");
    const auto& definition=c.continuations->program->data.at("entries").at(entry);
    capture_scope(captures,definition.at("captures"),true);
    Task task; task.entry=entry; task.self=c.self;
    task.frames.push_back(frame(0,index(definition.at("body")),{},std::move(captures)));
    run(c,*c.continuations,std::move(task));
}
void AdvanceContinuations(Ctx& c) {
    if(!c.continuations) return;
    auto& system=*c.continuations;
    check(!system.running,"Continuation advancement is already in progress");
    std::vector<int64_t> batch;
    for(const auto& [id,task]:system.pending) batch.push_back(id);
    for(const auto id:batch) {
        auto it=system.pending.find(id); if(it==system.pending.end()) continue;
        auto& task=it->second;
        if(!task.owner.empty() && !EntityExists(c,{task.owner})) { system.pending.erase(it); continue; }
        if(!task.owner.empty() && !IsEntityActive(c,{task.owner})) continue;
        const auto& s=instruction(system,task.wait);
        bool ready=false;
        try {
            Tick(c,s.at("node").get<std::string>());
            if(s.at("type")==2013) ready=std::get<bool>(evaluate(c,system,task,task.wait,1));
            else if(task.unscaled || !c.time_frozen) {
                const double step=task.unscaled ? c.unscaled_dt : c.dt;
                check(std::isfinite(step) && step>=0,"Invalid delay delta time");
                task.remaining=std::max(0.,task.remaining-step);
                ready=task.remaining<=4*std::numeric_limits<double>::epsilon()*std::max(1.,step);
                if(ready) task.remaining=0;
            }
        } catch(...) { system.pending.erase(it); throw; }
        if(ready) {
            Task resumed=std::move(task); system.pending.erase(it);
            ++resumed.frames.back().stack.back().pc;
            run(c,system,std::move(resumed));
        }
    }
}
void ForgetEntityContinuations(Ctx& c,const std::string& owner) {
    if(c.continuations) std::erase_if(c.continuations->pending,[&](const auto& p){return p.second.owner==owner;});
}
Json ContinuationCheckpoint(const Ctx& c) {
    if(!c.continuations) return nullptr;
    const auto& system=*c.continuations;
    check(!system.running,"Cannot checkpoint a running continuation");
    auto tasks=Json::array(); for(const auto& [id,task]:system.pending) tasks.push_back(task_json(task));
    Json saved={{"version",1},{"program",system.program->hash},{"next",system.next},{"tasks",tasks}};
    check(saved.dump().size()<=MaxBytes,"Pending continuations exceed 32 MiB"); return saved;
}
void RestoreContinuations(Ctx& target,const Ctx& source,const Json& saved) {
    if(!source.continuations) {
        check(saved.is_null(),"Checkpoint has unexpected continuations"); target.continuations.reset(); return;
    }
    check(saved.is_object() && saved.size()==4 && saved.at("version")==1 && saved.dump().size()<=MaxBytes,
          "Invalid continuation checkpoint");
    auto system=std::make_shared<Continuations>(); system->program=source.continuations->program;
    check(saved.at("program")==system->program->hash,"Continuation program mismatch");
    system->next=FromJson<int64_t>(saved.at("next")); check(system->next>0,"Invalid continuation serial");
    const auto& tasks=saved.at("tasks"); check(tasks.is_array() && tasks.size()<=MaxTasks,"Too many saved continuations");
    std::set<std::pair<std::string,std::string>> waiting;
    for(const auto& j:tasks) {
        Task task; task.id=FromJson<int64_t>(j.at("id")); task.entry=index(j.at("entry")); task.wait=index(j.at("wait"));
        check(task.id>0 && task.id<system->next,"Invalid saved continuation serial");
        task.self=FromJson<std::string>(j.at("self")); task.owner=FromJson<std::string>(j.at("owner"));
        check(task.owner.empty() || EntityExists(target,{task.owner}),"Unknown continuation owner");
        task.remaining=FromJson<double>(j.at("remaining")); task.unscaled=FromJson<bool>(j.at("unscaled"));
        check(task.remaining>=0,"Invalid remaining delay");
        const auto& entry=system->program->data.at("entries").at(task.entry);
        const auto& wait=instruction(*system,task.wait);
        check(wait.at("op")=="latent","Continuation must be suspended at a latent node");
        check(wait.at("type")!=2013 || (task.remaining==0 && !task.unscaled),"Wait Until has delay state");
        check(waiting.emplace(task.owner,wait.at("node").get<std::string>()).second,"Duplicate waiting node and owner");
        const auto& frames=j.at("frames");
        check(frames.is_array() && !frames.empty() && frames.size()<=MaxFrames,"Invalid continuation call depth");
        for(const auto& jf:frames) {
            Frame f; f.function=static_cast<int>(index(jf.at("function")));
            check(jf.at("parameters").is_array() && jf.at("locals").is_array(),"Invalid continuation captures");
            for(const auto& arg:jf.at("parameters")) f.parameters.push_back(unpacked(target,arg));
            for(const auto& local:jf.at("locals")) {
                check(local.is_object() && local.size()==3,"Invalid continuation local fields");
                check(f.locals.emplace(key(local),unpacked(target,local.at("value"))).second,"Duplicate continuation local");
            }
            const auto& stack=jf.at("stack");
            check(stack.is_array() && !stack.empty() && stack.size()<=MaxSegments && stack.size()%2==1,"Invalid continuation stack");
            for(const auto& js:stack) f.stack.push_back({js.at("kind").get<std::string>(),index(js.at("ref")),
                index(js.at("pc")),index(js.at("count")),unpacked(target,js.at("items"))});
            task.frames.push_back(std::move(f));
        }
        for(std::size_t fi=0;fi<task.frames.size();++fi) {
            auto& f=task.frames[fi];
            check((fi==0)==(f.function==0),"Invalid continuation function nesting");
            std::size_t root=index(entry.at("body"));
            if(fi==0) check(f.parameters.empty(),"Event continuation has function parameters");
            else {
                const auto& fn=system->program->data.at("functions").at(std::to_string(f.function));
                root=index(fn.at("body")); parameters(target,f.parameters,fn.at("inputs"));
            }
            check(f.stack.front().ref==root,"Invalid continuation root block");
            for(std::size_t si=0;si<f.stack.size();++si) {
                const auto& seg=f.stack[si];
                if(si%2==0) {
                    check(seg.kind=="block" && seg.count==0 && packed(seg.items)==packed(Value{Array<double>{}}),"Invalid continuation block fields");
                    check(seg.pc<=block(*system,seg.ref).size(),"Continuation position exceeds block");
                    continue;
                }
                const auto& previous=f.stack[si-1]; const auto& code=block(*system,previous.ref);
                check(previous.pc>0 && index(code.at(previous.pc-1))==seg.ref,"Continuation control does not follow its parent");
                const auto& s=instruction(*system,seg.ref); const auto node=s.at("node").get<std::string>();
                check(s.at("op")==seg.kind,"Continuation control kind mismatch");
                std::size_t child=0;
                if(seg.kind=="branch") {
                    check(seg.pc<2,"Invalid saved branch"); child=index(s.at(seg.pc ? "no" : "yes"));
                } else if(seg.kind=="switch") {
                    check(s.at("branches").size()==s.at("cases").size()+1,"Invalid Switch branch table");
                    child=index(s.at("branches").at(seg.pc));
                } else if(seg.kind=="flow") {
                    child=index(s.at("branches").at(seg.pc));
                    if(s.at("type")==2010) check(std::get<bool>(f.locals.at({node,"Is A"}))==(seg.pc==0),"Invalid captured Flip Flop route");
                    if(s.at("type")==2011) check(std::get<int64_t>(f.locals.at({node,"Index"}))==static_cast<int64_t>(seg.pc),"Invalid captured Multi Gate route");
                    if(s.at("type")==2008) check(std::get<int64_t>(f.locals.at({node,"Counter"}))>0,"Invalid captured Do N count");
                } else {
                    check(seg.kind=="for" || seg.kind=="foreach" || seg.kind=="while","Invalid continuation control");
                    child=index(s.at("body"));
                    if(seg.kind=="while") check(seg.pc==0,"Invalid saved While position");
                    else check(seg.pc>0 && seg.pc<=seg.count,"Invalid saved loop position");
                    if(seg.kind=="for") check(seg.count<=1000000,"Invalid saved For count");
                    if(seg.kind=="foreach") {
                        const auto items=IterationValues(seg.items);
                        const auto keys=IterationKeys(seg.items);
                        check(items.size()==seg.count,"Saved For Each array size mismatch");
                        check(std::get<int64_t>(f.locals.at({node,"Index"}))==static_cast<int64_t>(seg.pc-1) &&
                              packed(f.locals.at({node,"Item"}))==packed(items.at(seg.pc-1)),"Invalid captured For Each item");
                        if(!keys.empty())
                            check(std::get<std::string>(f.locals.at({node,"Key"}))==keys.at(seg.pc-1),"Invalid captured For Each map key");
                    }
                }
                if(seg.kind!="foreach") check(packed(seg.items)==packed(Value{Array<double>{}}),"Unexpected loop snapshot");
                if(seg.kind!="for" && seg.kind!="foreach") check(seg.count==0,"Unexpected loop count");
                check(f.stack[si+1].ref==child,"Continuation entered the wrong child block");
            }
            const auto& location=f.stack.back(); const auto& code=block(*system,location.ref);
            std::size_t current=0;
            if(fi+1<task.frames.size()) {
                check(location.pc>0,"Missing continuation function call"); current=index(code.at(location.pc-1));
                const auto& call=instruction(*system,current);
                check(call.at("op")=="function_call" && call.at("type")==task.frames[fi+1].function,"Invalid continuation caller");
            } else {
                current=index(code.at(location.pc)); check(current==task.wait,"Saved continuation is not at its wait instruction");
            }
            capture_scope(f.locals,instruction(*system,current).at("locals"),true);
        }
        check(task_json(task)==j,"Invalid or noncanonical continuation state");
        check(system->pending.emplace(task.id,std::move(task)).second,"Duplicate continuation serial");
    }
    // No callbacks or code from a save are installed. Bindings come from this program.
    target.continuations=std::move(system);
}
}
