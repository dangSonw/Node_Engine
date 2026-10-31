#include "runtime.hpp"
#include <fstream>
#include <iostream>
using namespace rt;
namespace {
Json checks=Json::array();
void check(bool okay,const std::string& name) { if(!okay) throw std::runtime_error(name); checks.push_back(name); }
template<class F> void rejects(F f) { bool failed=false; try { f(); } catch(const std::exception&) { failed=true; } if(!failed) throw std::runtime_error("Expected rejection"); }
Json scene() { return {{"version",1},{"entities",{{{"id","player"},{"position",{0,0,0}},{"rotation",{0,0,0}},{"scale",{1,1,1}}}}},{"variables",Json::object()}}; }
Json program() {
    Json statements=Json::array(); int type=2007;
    for(const auto* name:{"once","quota","gate","flip"}) statements.push_back({{"op","flow"},{"node",name},{"type",type++}});
    return {{"events",{{"start",statements},{"update",Json::array()}}}};
}
Ctx initial() { Ctx c; LoadScene(c,scene()); ConfigureFlow(c,program()); return c; }
Json trace(Ctx& c) {
    Json result=Json::array();
    for(int i=0;i<12;++i) {
        if(i==3) { DoOnceFlow(c,"once","Reset",{}); DoNFlow(c,"quota","Reset",{}); }
        if(i==5) GateFlow(c,"gate","Toggle",{},false);
        if(i==8) FlipFlopFlow(c,"flip","Reset",{});
        auto a=DoOnceFlow(c,"once","In",{}), b=DoNFlow(c,"quota","In",{},5),
             d=GateFlow(c,"gate","In",{},false), e=FlipFlopFlow(c,"flip","In",{});
        result.push_back({{"once",a.branch},{"count",b.count},{"quota",b.branch},{"gate",d.branch},{"flip",e.is_a},{"state",FlowCheckpoint(c)}});
    }
    return result;
}
void self_test() {
    auto c=initial();
    auto definitions=program();
    const Json data={{"op","flow"},{"node","payload"},{"type","not-a-node-type"}};
    definitions["events"]["start"][0]["args"]={{{"op","literal"},{"type","map<string>"},{"value",data}}};
    definitions["functions"]={{"1000000",{{"inputs",{{{"default",data}}}},{"body",Json::array()}}}};
    ConfigureFlow(c,definitions);
    check(c.flow_nodes.size()==4,"Map literals and function defaults are not instructions");
    check(DoOnceFlow(c,"once","In",{}).branch==0 && DoOnceFlow(c,"once","In",{}).branch==-1,"Do Once only admits first entry");
    DoOnceFlow(c,"once","Reset",{}); check(DoOnceFlow(c,"once","In",{}).branch==0,"Reset reopens Do Once");
    check(DoNFlow(c,"quota","In",{},0).branch==-1,"Do N zero does not execute");
    check(DoNFlow(c,"quota","In",{},2).count==1 && DoNFlow(c,"quota","In",{},2).count==2 && DoNFlow(c,"quota","In",{},2).branch==-1,"Do N stops at its exact quota");
    c.flow_states.at({"","quota"}).count=INT64_MAX-1;
    check(DoNFlow(c,"quota","In",{},INT64_MAX).count==INT64_MAX && DoNFlow(c,"quota","In",{},INT64_MAX).branch==-1,"Do N maximum integer does not overflow");
    DoNFlow(c,"quota","Reset",{},-1); check(DoNFlow(c,"quota","In",{},1).count==1,"Do N Reset ignores the unused limit");
    check(GateFlow(c,"gate","In",{},true).branch==-1,"Gate honors initial closed state");
    GateFlow(c,"gate","Open",{},true); check(GateFlow(c,"gate","In",{},true).branch==0,"Gate Open persists across initial-value inputs");
    GateFlow(c,"gate","Close",{},false); check(GateFlow(c,"gate","In",{},false).branch==-1,"Gate Close persists");
    GateFlow(c,"gate","Toggle",{},false); check(GateFlow(c,"gate","In",{},false).branch==0,"Gate Toggle opens closed gate");
    check(FlipFlopFlow(c,"flip","In",{}).is_a && !FlipFlopFlow(c,"flip","In",{}).is_a,"Flip Flop alternates A and B");
    FlipFlopFlow(c,"flip","In",{}); FlipFlopFlow(c,"flip","Reset",{}); check(FlipFlopFlow(c,"flip","In",{}).is_a,"Flip Flop Reset chooses A next");
    check(DoOnceFlow(c,"once","In",{"player"}).branch==0 && DoOnceFlow(c,"once","In",{}).branch==-1,"Entity and global states are independent");
    SetEntityActive(c,{"player"},false); DoOnceFlow(c,"once","Reset",{"player"}); SetEntityActive(c,{"player"},true);
    check(DoOnceFlow(c,"once","In",{"player"}).branch==0,"Explicit Reset works on inactive owner");
    auto copy=CloneEntity(c,{"player"},"copy"); check(DoOnceFlow(c,"once","In",copy).branch==0,"Clone starts fresh owner flow state");
    DestroyEntity(c,copy); check(!c.flow_states.contains({copy.id,"once"}),"Destroy erases owned flow state");
    const auto saved=FlowCheckpoint(c); auto restored=initial(); RestoreFlow(restored,saved);
    check(FlowCheckpoint(restored)==saved,"Flow checkpoint roundtrips exactly");
    for(int damage=0;damage<9;++damage) {
        auto bad=saved;
        if(damage==0) bad["bindings"]["once"]=2008;
        if(damage==1) bad["states"][0]["node"]="missing";
        if(damage==2) bad["states"][0]["owner"]="missing";
        if(damage==3) bad["states"][0]["count"]=-1;
        if(damage==4) bad["states"][0]["flag"]=1;
        if(damage==5) bad["states"].push_back(bad["states"][0]);
        if(damage==6) bad["extra"]=0;
        if(damage==7) bad["states"][0]["count"]=2; // flip alphabetically first: count must be zero.
        if(damage==8) { auto entry=bad["states"][0]; bad["states"]=Json::array(); for(int i=0;i<4097;++i) bad["states"].push_back(entry); }
        rejects([&]{RestoreFlow(restored,bad);}); check(FlowCheckpoint(restored)==saved,"Malformed flow checkpoint rejects atomically: "+std::to_string(damage));
    }
    check(trace(c)==trace(restored),"Restored gates reproduce future decisions and state");
    const auto before=FlowCheckpoint(c);
    rejects([&]{DoNFlow(c,"quota","In",{},-1);}); rejects([&]{DoOnceFlow(c,"missing","In",{});});
    rejects([&]{GateFlow(c,"gate","Reset",{},false);}); rejects([&]{FlipFlopFlow(c,"flip","In",{"missing"});});
    check(FlowCheckpoint(c)==before,"Invalid control calls leave state unchanged");
    LoadScene(c,scene()); check(c.flow_nodes.empty() && c.flow_states.empty(),"LoadScene resets flow bindings and values");
}
}
int main(int argc,char** argv) {
    try {
        if(argc==1) self_test();
        else if(argc==3 && std::string(argv[1])=="--write") {
            auto c=initial(); trace(c); auto saved=FlowCheckpoint(c); auto future=trace(c);
            std::ofstream out(std::filesystem::u8path(argv[2])); out<<Json({{"saved",saved},{"future",future}}).dump(); out.close();
            check(bool(out),"Write flow checkpoint and reference trace");
        } else if(argc==3 && std::string(argv[1])=="--read") {
            std::ifstream in(std::filesystem::u8path(argv[2])); Json data; in>>data;
            auto c=initial(); RestoreFlow(c,data.at("saved")); check(trace(c)==data.at("future"),"Fresh-process future flow decisions match reference");
        } else throw std::runtime_error("Usage: node_flow_probe [--write FILE | --read FILE]");
        std::cout<<Json({{"passed",true},{"checks",checks}}).dump()<<'\n';
    } catch(const std::exception& e) { std::cout<<Json({{"passed",false},{"checks",checks},{"error",e.what()}}).dump()<<'\n'; return 1; }
}
