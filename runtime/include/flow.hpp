#pragma once
#include "values.hpp"
#include <map>
#include <set>
#include <algorithm>
#include <string>

namespace rt {
struct Ctx;
template<class Yes,class No> auto SelectValue(bool condition,Yes yes,No no) {
    return condition ? yes() : no();
}
template<class T> std::size_t SwitchBranch(const T& value,const Array<T>& cases) {
    static_assert(std::is_same_v<T,std::int64_t> || std::is_same_v<T,std::string>);
    if(cases.size()>256) throw std::runtime_error("Switch exceeds 256 cases");
    std::set<T> seen;
    for(const auto& item:cases)
        if(!seen.insert(item).second) throw std::runtime_error("Duplicate Switch case");
    const auto found=std::find(cases.begin(),cases.end(),value);
    return static_cast<std::size_t>(found-cases.begin());
}
std::size_t DispatchSwitch(const Value&,const Json& cases);
struct FlowState { std::int64_t count=0; bool flag=false; int branches=0,used=0,next=0; };
struct FlowResult { int branch=-1; std::int64_t count=0; bool is_a=false; std::int64_t index=-1; };
void ConfigureFlow(Ctx&,const Json& program);
FlowResult DoOnceFlow(Ctx&,const std::string& node,const std::string& input,EntityRef owner);
FlowResult DoNFlow(Ctx&,const std::string& node,const std::string& input,EntityRef owner,std::int64_t limit=0);
FlowResult GateFlow(Ctx&,const std::string& node,const std::string& input,EntityRef owner,bool start_closed);
FlowResult FlipFlopFlow(Ctx&,const std::string& node,const std::string& input,EntityRef owner);
FlowResult MultiGateFlow(Ctx&,const std::string& node,const std::string& input,EntityRef owner,
                        std::int64_t branches=2,bool random=false,bool loop=false,std::int64_t start=-1);
FlowResult DispatchFlow(Ctx&,int type,const std::string& node,const std::string& input,const std::vector<Value>& args);
void ForgetEntityFlow(Ctx&,const std::string& owner);
Json FlowCheckpoint(const Ctx&);
void RestoreFlow(Ctx&,const Json&);
}
