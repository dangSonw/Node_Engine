// Native checkpoint acceptance probe; callbacks always come from this executable.
#include "runtime.hpp"
#include <flecs.h>
#include <filesystem>
#include <fstream>
#include <iostream>

using namespace rt;
namespace {
Json checks=Json::array();
void Require(bool ok,const std::string& message) {
    if(!ok) throw std::runtime_error(message);
}
void Check(const std::string& name,bool ok) { Require(ok,name); checks.push_back(name); }
template<class F> std::string Failure(F operation) {
    try { operation(); } catch(const std::exception& e) { return e.what(); }
    throw std::runtime_error("Expected operation to fail");
}
Json EntityData(const std::string& id) {
    return {{"id",id},{"position",{0,0,0}},{"rotation",{0,0,0}},{"scale",{1,1,1}}};
}
Json Scene() {
    Json entities=Json::array();
    for(const auto* id:{"player","inactive","deleted","sender"}) entities.push_back(EntityData(id));
    return {{"version",1},{"entities",entities},{"variables",Json::object()}};
}
std::vector<Value> Payload() {
    return {1.25,std::int64_t(INT64_MIN),true,std::string("Việt\0😀",12),Vec3(1.5,-2,3),EntityRef{"sender"},
        Array<double>{1.25},Array<std::int64_t>{INT64_MIN,INT64_MAX},Array<bool>{true,false},
        Array<std::string>{"điểm"},Array<Vec3>{Vec3(1.5,-2,3)},Array<EntityRef>{{"sender"}},
        Map<double>{{"κ",1.25}},Map<std::int64_t>{{"κ",INT64_MAX}},Map<bool>{{"κ",true}},
        Map<std::string>{{"κ",std::string("a\0z",3)}},Map<Vec3>{{"κ",Vec3(1.5,-2,3)}},Map<EntityRef>{{"κ",{"sender"}}}};
}
void BindProgram(Ctx& c) {
    DeclareEvent(c,100001,{"int"});
    std::vector<std::string> types;
    for(const auto& v:Payload()) types.push_back(std::visit([](const auto& x){return TypeName<std::decay_t<decltype(x)>>();},v));
    DeclareEvent(c,100002,std::move(types));
    for(const std::string owner:{"","player","inactive","deleted"}) {
        for(const std::string node:{"z","a"}) {
            BindEvent(c,100001,node,{owner},true,[node](Ctx& ctx,EntityRef sender,EntityRef receiver,const std::vector<Value>& args) {
                Print(ctx,"event:"+node+":"+sender.id+":"+receiver.id+":"+std::to_string(std::get<std::int64_t>(args.at(0))));
            });
            BindTimer(c,node,{owner},"",[node](Ctx& ctx,const std::string& name,EntityRef receiver) {
                Print(ctx,"timer:"+node+":"+receiver.id+":"+name);
                if(node=="a") SendEvent(ctx,100001,{},{},{std::int64_t(40)});
            });
        }
    }
    BindEvent(c,100002,"types",{},true,[](Ctx& ctx,EntityRef sender,EntityRef,const std::vector<Value>& args) {
        Json typed=Json::array(); for(const auto& v:args) typed.push_back(VariableJson(v));
        Print(ctx,"types:"+sender.id+":"+typed.dump());
    });
}
Ctx Initial() {
    Ctx c; LoadScene(c,Scene()); BindProgram(c);
    c.current_node="start-timers";
    StartTimer(c,"z-first",.5,false,{}); StartTimer(c,"a-second",.5,false,{});
    StartTimer(c,"repeat",.125,true,{"player"}); StartTimer(c,"paused",.3,true,{});
    StartTimer(c,"suspended",.23,true,{"inactive"}); StartTimer(c,"deleted",.01,true,{"deleted"});
    StartTimer(c,"unscaled",.17,true,{},true); StartTimer(c,"unscaled-paused",.19,true,{},true);
    StartTimer(c,"unscaled-owned",.23,true,{"inactive"},true); StartTimer(c,"unscaled-deleted",.1,true,{"deleted"},true);
    c.dt=.037; AdvanceTimers(c); DrainEvents(c);
    PauseTimer(c,"paused",{}); SetEntityActive(c,{"inactive"},false);
    PauseTimer(c,"unscaled-paused",{});
    c.current_node="queue-origin";
    SendEvent(c,100001,{"player"},{"sender"},{std::int64_t(1)});
    SetEventSubscription(c,100001,{"player"},false); SetEventSubscription(c,100001,{"player"},true);
    SendEvent(c,100001,{"player"},{"sender"},{std::int64_t(2)});
    BroadcastEvent(c,100001,{"sender"},{std::int64_t(3)});
    SendEvent(c,100002,{},{"sender"},Payload());
    DestroyEntity(c,{"sender"}); DestroyEntity(c,{"deleted"});
    c.logs.clear(); return c;
}
Json Continue(Ctx& c) {
    Json frames=Json::array();
    DrainEvents(c);
    const std::vector<std::string> expected={"event:a:sender:player:2","event:z:sender:player:2",
        "event:a:sender::3","event:z:sender::3","event:a:sender:player:3","event:z:sender:player:3"};
    Require(c.logs.size()==7 && std::equal(expected.begin(),expected.end(),c.logs.begin()),"FIFO, cancellation and listener order");
    Json typed=Json::array(); for(const auto& v:Payload()) typed.push_back(VariableJson(v));
    Require(c.logs.back()=="types:sender:"+typed.dump(),"All 18 typed payloads and deleted sender survive");
    for(int frame=0;frame<160;++frame) {
        c.remaining=c.budget;
        if(frame==5) ResumeTimer(c,"paused",{});
        if(frame==6) ResumeTimer(c,"unscaled-paused",{});
        if(frame==8) SetEntityActive(c,{"inactive"},true);
        if(frame==12) SetEntityActive(c,{"player"},false);
        if(frame==16) SetEntityActive(c,{"player"},true);
        if(frame==20) SetEventSubscription(c,100001,{"player"},false);
        if(frame==24) SetEventSubscription(c,100001,{"player"},true);
        if(frame==45) BroadcastEvent(c,100001,{},{std::int64_t(5)});
        c.dt=frame%4==0 ? 0 : frame%4==1 ? .013 : frame%4==2 ? 1./60 : .1;
        AdvanceTimers(c); DrainEvents(c);
        frames.push_back({{"events",EventCheckpoint(c)},{"logs",c.logs}}); c.logs.clear();
    }
    return frames;
}
int Alive(Ctx& c) { return ecs_get_entities(NativeWorld(c)).alive_count; }
void Malformed() {
    auto source=Initial(); auto saved=Json::parse(EventCheckpoint(source).dump());
    Ctx target; LoadScene(target,Snapshot(source).at("scene"));
    RestoreEventCheckpoint(target,source,saved);
    Check("exact checkpoint roundtrip in a distinct native world",EventCheckpoint(target)==saved && NativeWorld(target)!=NativeWorld(source));
    const auto before=EventCheckpoint(target),scene=Snapshot(target); const auto handle=target.events; const auto count=Alive(target);
    using Damage=std::function<void(Json&)>;
    const std::vector<std::pair<std::string,Damage>> cases={
        {"version",[](Json& j){j["version"]=3;}},
        {"fractional version",[](Json& j){j["version"]=1.0;}},
        {"extra fields",[](Json& j){j["unknown"]=0;}},
        {"missing fields",[](Json& j){j.erase("clock");}},
        {"binding identity",[](Json& j){j["bindings"]["timers"][0]["listeners"][0]["node"]="injected";}},
        {"negative clock",[](Json& j){j["clock"]="-1";}},
        {"infinite clock",[](Json& j){j["clock"]="1e10000";}},
        {"trailing clock data",[](Json& j){j["clock"]="1abc";}},
        {"clock whitespace",[](Json& j){j["clock"]=" 1";}},
        {"numeric clock",[](Json& j){j["clock"]=1;}},
        {"negative unscaled clock",[](Json& j){j["unscaled_clock"]="-1";}},
        {"missing unscaled clock",[](Json& j){j.erase("unscaled_clock");}},
        {"invalid timer clock mode",[](Json& j){j["timers"][0]["unscaled"]="true";}},
        {"missing timer clock mode",[](Json& j){j["timers"][0].erase("unscaled");}},
        {"negative sequence",[](Json& j){j["serial"]=-1;}},
        {"fractional sequence",[](Json& j){j["serial"]=1.5;}},
        {"duplicate timer",[](Json& j){j["timers"].push_back(j["timers"][0]);}},
        {"unknown timer owner",[](Json& j){j["timers"][0]["owner"]="missing";}},
        {"empty timer name",[](Json& j){j["timers"][0]["name"]="";}},
        {"zero timer sequence",[](Json& j){j["timers"][0]["serial"]=0;}},
        {"future timer sequence",[](Json& j){j["timers"][0]["serial"]=j["serial"].get<std::uint64_t>()+1;}},
        {"zero repeat interval",[](Json& j){j["timers"][0]["repeat"]=true;j["timers"][0]["interval"]="0";}},
        {"timer activity mismatch",[](Json& j){j["timers"][0]["suspended"]=true;}},
        {"origin with NUL",[](Json& j){j["timers"][0]["origin"]=std::string("a\0b",3);}},
        {"duplicate receiver",[](Json& j){j["receivers"][1]=j["receivers"][0];}},
        {"receiver activity mismatch",[](Json& j){j["receivers"][0]["active"]=false;}},
        {"duplicate subscription",[](Json& j){j["subscriptions"][1]=j["subscriptions"][0];}},
        {"subscription epoch",[](Json& j){j["subscriptions"][0]["activity_epoch"]=10000;}},
        {"unknown event",[](Json& j){j["queue"][0]["event"]=199999;}},
        {"unknown recipient",[](Json& j){j["queue"][0]["receiver"]="missing";}},
        {"payload type",[](Json& j){j["queue"][0]["args"][0]="wrong";}},
        {"payload count",[](Json& j){j["queue"][0]["args"].push_back(1);}},
        {"future queue epoch",[](Json& j){j["queue"][0]["epoch"]=10000;}},
        {"queue limit",[](Json& j){auto e=j["queue"][0];j["queue"]=Json::array();for(int i=0;i<4097;++i)j["queue"].push_back(e);}},
        {"timer limit",[](Json& j){auto t=j["timers"][0];j["timers"]=Json::array();for(int i=0;i<4097;++i)j["timers"].push_back(t);}},
        {"queue memory limit",[](Json& j){auto e=j["queue"].back();e["args"][3]=std::string(MaxString,'x');j["queue"]=Json::array();for(int i=0;i<65;++i)j["queue"].push_back(e);}}
    };
    for(const auto& [name,damage]:cases) {
        auto bad=saved; damage(bad); Failure([&]{RestoreEventCheckpoint(target,source,bad);});
        Check("reject "+name+" without mutation or live Flecs leaks",target.events==handle && EventCheckpoint(target)==before && Snapshot(target)==scene && Alive(target)==count);
    }
    // Source and destination may be the same Ctx; staged observers must replace the old ones.
    auto same=Initial(); const auto same_before=EventCheckpoint(same); const auto same_count=Alive(same);
    RestoreEventCheckpoint(same,same,same_before); const auto stable_count=Alive(same);
    for(int i=0;i<12;++i) RestoreEventCheckpoint(same,same,EventCheckpoint(same));
    Check("repeated in-place replacement does not accumulate native entities",Alive(same)==stable_count && stable_count<=same_count && EventCheckpoint(same)==same_before);
    Check("160-frame continuation equals uninterrupted execution",Continue(target)==Continue(source));
}
void Boundaries() {
    Ctx c; LoadScene(c,Scene());
    bool event_rejected=false,timer_rejected=false;
    DeclareEvent(c,100001,{});
    Json saved;
    BindEvent(c,100001,"event-boundary",{},true,[&](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>&) {
        const auto a=Failure([&]{EventCheckpoint(ctx);});
        const auto b=Failure([&]{RestoreEventCheckpoint(ctx,ctx,saved);});
        event_rejected=a.find("boundary")!=std::string::npos && b.find("boundary")!=std::string::npos;
        throw std::runtime_error("handler error");
    });
    BindTimer(c,"timer-boundary",{},"",[&](Ctx& ctx,const std::string&,EntityRef) {
        const auto a=Failure([&]{EventCheckpoint(ctx);});
        const auto b=Failure([&]{RestoreEventCheckpoint(ctx,ctx,saved);});
        const auto d=Failure([&]{AdvanceTimers(ctx);});
        timer_rejected=a.find("boundary")!=std::string::npos && b.find("boundary")!=std::string::npos && d.find("in progress")!=std::string::npos;
        throw std::runtime_error("timer error");
    });
    saved=EventCheckpoint(c);
    SendEvent(c,100001,{},{},{}); Failure([&]{DrainEvents(c);});
    Check("checkpoint/restore rejected inside custom callback and guard cleared after error",event_rejected && EventCheckpoint(c)["queue"].empty());
    StartTimer(c,"test",0,false,{}); Failure([&]{AdvanceTimers(c);});
    Check("checkpoint/restore/nested advance rejected inside timer and guard cleared after error",timer_rejected && EventCheckpoint(c)["timers"].empty());
    RestoreEventCheckpoint(c,c,saved);
    Check("restore remains usable after dispatch errors",EventCheckpoint(c)==saved);
}
void Budget() {
    auto c=Initial(); const auto saved=EventCheckpoint(c);
    RestoreEventCheckpoint(c,c,saved); c.remaining=0;
    const auto queue_error=Failure([&]{DrainEvents(c);});
    Check("restored canceled envelope consumes budget at original node",queue_error.find("queue-origin")!=std::string::npos && EventCheckpoint(c)["queue"].empty());
    RestoreEventCheckpoint(c,c,saved); c.remaining=0; c.dt=1;
    const auto timer_error=Failure([&]{AdvanceTimers(c);});
    Check("restored timer consumes budget at original node",timer_error.find("start-timers")!=std::string::npos);
}
void Prefab() {
    auto scene=Scene(); auto root=EntityData("root"),child=EntityData("child"); child["parent"]="root";
    Json asset={{"id","test"},{"version",1},{"root","root"},{"entities",{root,child}}};
    scene["prefab_assets"]={asset}; scene["prefab_templates"]={asset};
    Ctx original; LoadScene(original,scene); auto instance=InstantiatePrefab(original,"test",{},Vec3(0));
    const auto member=GetPrefabEntity(original,instance,"child");
    DeclareEvent(original,100001,{});
    BindEvent(original,100001,"reborn-event",member,true,[](Ctx& c,EntityRef,EntityRef,const std::vector<Value>&){Print(c,"reborn event");});
    BindTimer(original,"reborn-timer",member,"",[](Ctx& c,const std::string&,EntityRef){Print(c,"reborn timer");});
    DestroyEntity(original,member);
    const auto checkpoint=EventCheckpoint(original);
    Ctx restored; LoadScene(restored,Snapshot(original)["scene"]); RestoreEventCheckpoint(restored,original,checkpoint);
    ResetPrefabInstance(restored,instance,true);
    Require(EntityExists(restored,member),"Prefab reset restores stable member ID");
    SetEventSubscription(restored,100001,member,true); SendEvent(restored,100001,member,{},{});
    StartTimer(restored,"reborn",0,false,member); DrainEvents(restored); AdvanceTimers(restored);
    Check("destroyed owner checkpoint keeps bindings for later prefab recreation",restored.logs==std::vector<std::string>{"reborn event","reborn timer"});
}
void ClockDomains() {
    Ctx original; LoadScene(original,Scene()); BindProgram(original);
    StartTimer(original,"game",.19,true,{});
    StartTimer(original,"menu",.13,true,{},true);
    StartTimer(original,"paused-menu",.17,true,{"player"},true);
    BeginGameFrame(original,.07); AdvanceTimers(original); DrainEvents(original);
    PauseTimer(original,"paused-menu",{"player"});
    SetTimeScale(original,0); BeginGameFrame(original,.11); AdvanceTimers(original); DrainEvents(original);
    auto checkpoint=EventCheckpoint(original); original.logs.clear();
    Check("checkpoint captures distinct game and unscaled clocks",checkpoint["clock"]!=checkpoint["unscaled_clock"]);
    Ctx restored; LoadScene(restored,Snapshot(original)["scene"]);
    RestoreEventCheckpoint(restored,original,checkpoint);
    Check("mixed timers roundtrip exactly",EventCheckpoint(restored)==checkpoint);
    for(int frame=0;frame<120;++frame) {
        for(auto* c:{&original,&restored}) {
            c->remaining=c->budget;
            if(frame==3) ResumeTimer(*c,"paused-menu",{"player"});
            if(frame==7) SetEntityActive(*c,{"player"},false);
            if(frame==13) SetEntityActive(*c,{"player"},true);
            SetTimeScale(*c,frame<20 ? 0 : frame%3==0 ? 2 : .25);
            BeginGameFrame(*c,frame%2==0 ? .013 : .031);
            AdvanceTimers(*c); DrainEvents(*c);
        }
        Require(EventCheckpoint(original)==EventCheckpoint(restored) && original.logs==restored.logs,"mixed timer continuation diverged");
    }
    Check("120-frame dual-clock continuation including manual and owner pause",true);
    auto legacy=checkpoint; legacy["version"]=1; legacy.erase("unscaled_clock");
    for(auto& timer:legacy["timers"]) timer.erase("unscaled");
    RestoreEventCheckpoint(restored,original,legacy);
    const auto migrated=EventCheckpoint(restored);
    bool scaled=true; for(const auto& timer:migrated["timers"]) scaled&=!timer["unscaled"].get<bool>();
    Check("legacy event checkpoint preserves timers as scaled",migrated["version"]==2 && migrated["unscaled_clock"]==legacy["clock"] && scaled);
    auto before=EventCheckpoint(restored); restored.unscaled_dt=-1;
    Failure([&]{AdvanceTimers(restored);});
    Check("invalid unscaled delta cannot advance either timer clock",EventCheckpoint(restored)==before);
}
void AnimationEvents() {
    auto scene=Scene(); auto root=EntityData("root"),child=EntityData("child"); child["parent"]="root";
    Json asset={{"id","test"},{"version",1},{"root","root"},{"entities",{root,child}}};
    scene["prefab_assets"]={asset}; scene["prefab_templates"]={asset};
    Ctx source; LoadScene(source,scene); const auto instance=InstantiatePrefab(source,"test",{},Vec3(0));
    const auto member=GetPrefabEntity(source,instance,"child");
    auto callback=[](Ctx& c,EntityRef,EntityRef receiver,const std::vector<Value>& args) {
        Print(c,receiver.id+":"+std::get<EntityRef>(args.at(0)).id+":"+std::get<std::string>(args.at(1)));
    };
    BindAnimationFinished(source,"global",{},"Wave",callback);
    BindAnimationFinished(source,"member",member,"",callback);
    QueueAnimationFinished(source,member,"Wave"); QueueAnimationFinished(source,member,"Idle");
    const auto checkpoint=EventCheckpoint(source);
    Ctx target; LoadScene(target,Snapshot(source)["scene"]); RestoreEventCheckpoint(target,source,checkpoint);
    Check("animation queued payloads and clip filters restore exactly",EventCheckpoint(target)==checkpoint);
    DrainEvents(source); DrainEvents(target);
    Check("restored animation callbacks retain filters and entity scope",target.logs==source.logs && target.logs.size()==3 &&
        target.logs.front()==":"+member.id+":Wave" && target.logs.back()==member.id+":"+member.id+":Idle");
    const auto before=EventCheckpoint(target); const auto handle=target.events; const auto count=Alive(target);
    auto bad=checkpoint; bad["bindings"]["events"][0]["listeners"][0]["filter"]="Idle";
    Failure([&]{RestoreEventCheckpoint(target,source,bad);});
    Check("different animation filter rejects without changing target",target.events==handle && EventCheckpoint(target)==before && Alive(target)==count);
    for(auto& entry:bad["subscriptions"]) entry["enabled"]=false;
    bad["bindings"]=checkpoint["bindings"];
    Failure([&]{RestoreEventCheckpoint(target,source,bad);});
    Check("disabled builtin animation subscription rejects atomically",target.events==handle && EventCheckpoint(target)==before && Alive(target)==count);
    bad=checkpoint; bad["queue"][0]["args"][1]=1;
    Failure([&]{RestoreEventCheckpoint(target,source,bad);});
    Check("wrong animation payload type rejects atomically",target.events==handle && EventCheckpoint(target)==before && Alive(target)==count);
    for(const auto& filter:{std::string(513,'x'),std::string("a\0b",3)})
        Failure([&]{BindAnimationFinished(target,"bad",{},filter,callback);});
    Check("invalid native clip filters do not add bindings",EventCheckpoint(target)==before);
    QueueAnimationFinished(source,member,"Wave"); DestroyEntity(source,member);
    const auto missing=EventCheckpoint(source); target.logs.clear();
    Ctx restored; LoadScene(restored,Snapshot(source)["scene"]); RestoreEventCheckpoint(restored,source,missing);
    DrainEvents(restored);
    Check("destroy cancels owner completion and retains captured global payload",restored.logs==std::vector<std::string>{":"+member.id+":Wave"});
    ResetPrefabInstance(restored,instance,true); QueueAnimationFinished(restored,member,"Idle"); DrainEvents(restored);
    Check("prefab recreation reactivates restored animation subscription",restored.logs.back()==member.id+":"+member.id+":Idle" && restored.logs.size()==2);
    QueueAnimationFinished(restored,member,"Idle"); SetEntityActive(restored,member,false); SetEntityActive(restored,member,true);
    DrainEvents(restored);
    Check("activity epoch cancels stale queued animation callbacks",restored.logs.size()==2);
}
void EntityLifecycleEvents() {
    Ctx source; LoadScene(source,Scene());
    for(int type:{1006,1007,1008}) for(const std::string owner:{"","player"})
        BindEntityLifecycle(source,type,"listener",{owner},[type](Ctx& c,EntityRef,EntityRef receiver,const std::vector<Value>& args) {
            Print(c,std::to_string(type)+":"+receiver.id+":"+std::get<EntityRef>(args.at(0)).id+":"+(std::get<bool>(args.at(1))?"true":"false"));
        });
    Check("scene construction does not dispatch lifecycle callbacks",source.logs.empty() && EventCheckpoint(source)["queue"].empty());
    Check("fresh lifecycle checkpoint has explicit not-started state",EventCheckpoint(source)["version"]==3 && !EventCheckpoint(source)["lifecycle_started"].get<bool>());
    StartEntityLifecycle(source); DrainEvents(source);
    Check("initial global and owned lifecycle callbacks run once",source.logs.size()==10);
    source.logs.clear(); StartEntityLifecycle(source); RefreshEntityActivity(source);
    Check("repeated lifecycle start and activity refresh are idempotent",EventCheckpoint(source)["queue"].empty());
    for(bool active:{false,true,false}) SetEntityActive(source,{"player"},active);
    const auto spawned=SpawnEntity(source,"temporary","",Vec3(0)); DestroyEntity(source,spawned);
    const auto checkpoint=EventCheckpoint(source);
    Check("rapid toggles retain disabled owned deliveries and dead global creation payloads",checkpoint["queue"].size()==8);
    Ctx target; LoadScene(target,Snapshot(source)["scene"],SceneIdentityCheckpoint(source));
    RestoreEventCheckpoint(target,source,checkpoint);
    Check("lifecycle queue and bindings roundtrip exactly",EventCheckpoint(target)==checkpoint);
    StartEntityLifecycle(target); RefreshEntityActivity(target);
    Check("restored lifecycle baseline emits no duplicate initial events",EventCheckpoint(target)==checkpoint);
    const auto handle=target.events; const auto count=Alive(target);
    for(int damage=0;damage<9;++damage) {
        auto bad=checkpoint;
        if(damage==0) { bad["version"]=2; bad.erase("lifecycle_started"); }
        if(damage==1) bad["lifecycle_started"]=false;
        if(damage==2) bad["subscriptions"][1]["active"]=false;
        if(damage==3) bad["subscriptions"][1]["enabled"]=false;
        if(damage==4) bad["queue"][1]["args"][0]="different";
        if(damage==5) bad["queue"][0]["args"][1]=true;
        if(damage==6) bad["queue"][0]["sender"]="player";
        if(damage==7) bad["queue"][0]["args"][0]="";
        if(damage==8) bad["queue"][0]["args"][1]="false";
        Failure([&]{RestoreEventCheckpoint(target,source,bad);});
        Check("malformed lifecycle checkpoint rejects without world or observer leaks: "+std::to_string(damage),
            target.events==handle && EventCheckpoint(target)==checkpoint && Alive(target)==count);
    }
    DrainEvents(source); DrainEvents(target);
    Check("restored lifecycle payloads dispatch identically including inactive receivers",target.logs==source.logs && target.logs.size()==8);
    for(auto* c:{&source,&target}) { c->logs.clear(); SetEntityActive(*c,{"player"},true); DrainEvents(*c); }
    Check("activity tracking continues after restoration",source.logs==target.logs && source.logs.size()==2);
    SetEntityActive(target,{"player"},false); DestroyEntity(target,{"player"});
    const auto missing=EventCheckpoint(target);
    Ctx restored; LoadScene(restored,Snapshot(target)["scene"],SceneIdentityCheckpoint(target)); RestoreEventCheckpoint(restored,target,missing);
    DrainEvents(restored);
    Check("removed lifecycle owner stays cancelled across restoration",restored.logs==std::vector<std::string>{"1008::player:false"});
    Ctx bounded; LoadScene(bounded,Scene()); BindEntityLifecycle(bounded,1008,"disabled",{},[](Ctx&,EntityRef,EntityRef,const std::vector<Value>&){});
    StartEntityLifecycle(bounded);
    for(int i=0;i<4096;++i) { SetEntityActive(bounded,{"player"},false); SetEntityActive(bounded,{"player"},true); }
    auto error=Failure([&]{SetEntityActive(bounded,{"player"},false);});
    Check("lifecycle shares the bounded event queue",error.find("4096")!=std::string::npos && EventCheckpoint(bounded)["queue"].size()==4096);
}
void PhysicsPrefabLifecycle() {
    auto scene=Scene(); scene["entities"][0]["scale"]={1,2,1};
    auto root=EntityData("root"), child=EntityData("child"); child["parent"]="root";
    root["rigid_body"]={{"shape","sphere"},{"motion","dynamic"},{"half_extents",{.5,.5,.5}},{"radius",.5},
        {"half_height",.5},{"mass",1.},{"friction",.5},{"restitution",0.},{"gravity_scale",1.},
        {"linear_damping",.05},{"angular_damping",.05},{"mask",4294967295ULL},
        {"sensor",false},{"continuous",false},{"enabled",true}};
    Json asset={{"id","body"},{"version",1},{"root","root"},{"entities",{root,child}}};
    scene["prefab_assets"]={asset}; scene["prefab_templates"]={asset};
    Ctx c; LoadScene(c,scene);
    for(int type:{1006,1007,1008}) BindEntityLifecycle(c,type,"global",{},[type](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>& args) {
        Print(ctx,std::to_string(type)+":"+std::get<EntityRef>(args.at(0)).id);
    });
    StartEntityLifecycle(c); DrainEvents(c); c.logs.clear();
    const auto before=Snapshot(c), events=EventCheckpoint(c), identity=SceneIdentityCheckpoint(c);
    Failure([&]{InstantiatePrefab(c,"body",{"player"},Vec3(0));});
    Check("failed staged physics prefab emits no lifecycle and preserves live scene",Snapshot(c)==before && EventCheckpoint(c)==events && SceneIdentityCheckpoint(c)==identity);
    const auto instance=InstantiatePrefab(c,"body",{},Vec3(0)); const auto member=GetPrefabEntity(c,instance,"child");
    DrainEvents(c);
    Check("staged physics prefab emits only committed creation and enable once",c.logs.size()==4 && c.physics_scene.bodies.contains(instance.id));
    c.logs.clear(); SetEntityActive(c,instance,false); DrainEvents(c); ResetPrefabInstance(c,instance,true); DrainEvents(c);
    Check("physics prefab reset compares final inherited activity once",c.logs==std::vector<std::string>{"1008:"+instance.id,"1008:"+member.id,"1007:"+instance.id,"1007:"+member.id});
    c.logs.clear(); DestroyEntity(c,member); ResetPrefabInstance(c,instance,true); DrainEvents(c);
    Check("physics prefab reset recreates one member without duplicate staging events",c.logs==std::vector<std::string>{"1006:"+member.id,"1007:"+member.id});
    Ctx d; LoadScene(d,scene);
    const auto first=InstantiatePrefab(d,"body",{},Vec3(0)), second=InstantiatePrefab(d,"body",{},Vec3(3,0,0));
    const auto extra=SpawnEntity(d,"extra","",Vec3(0)); SetParent(d,extra,first);
    BindEntityLifecycle(d,1009,"before-reset",{},[extra,second](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>& args) {
        const auto entity=std::get<EntityRef>(args.at(0));
        Require(entity==extra && EntityExists(ctx,entity),"Reset must notify its still-live addition");
        Print(ctx,GetEntityName(ctx,entity)); SetBodyVelocity(ctx,second,Vec3(3,1,0));
        SpawnEntity(ctx,"loot","",Vec3(0));
    });
    StartEntityLifecycle(d);
    const auto unchanged=Snapshot(d), untouched=EventCheckpoint(d);
    Failure([&]{InstantiatePrefab(d,"body",{"player"},Vec3(0));});
    Check("invalid physics edit with destruction listeners fails before callbacks",Snapshot(d)==unchanged && EventCheckpoint(d)==untouched);
    ResetPrefabInstance(d,first,true);
    Check("before-delete physics prefab callback reads original state once",d.logs==std::vector<std::string>{"extra"} && !EntityExists(d,extra));
    Check("physics prefab revalidation preserves callback velocity and spawned loot",GetBodyVelocity(d,second)==Vec3(3,1,0) && FindEntitiesByName(d,"loot").size()==1);
}
void DestroyedEvents() {
    Ctx c; LoadScene(c,Scene());
    BindEntityLifecycle(c,1009,"global",{},[](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>& args) {
        const auto entity=std::get<EntityRef>(args.at(0));
        Require(EntityExists(ctx,entity),"Destroyed entity must still exist during callback");
        Require(!Failure([&]{EventCheckpoint(ctx);}).empty(),"Inline callback needs checkpoint boundary");
        Print(ctx,"global:"+GetEntityName(ctx,entity));
    });
    BindEntityLifecycle(c,1009,"owned",{"player"},[](Ctx& ctx,EntityRef,EntityRef receiver,const std::vector<Value>&) {
        Require(ctx.self=="player" && receiver.id=="player","Owned destroy Self");
        DestroyEntity(ctx,receiver); DestroyEntity(ctx,{"sender"});
        Require(EntityExists(ctx,receiver) && EntityExists(ctx,{"sender"}),"Nested deletion must wait for callback completion");
        SpawnEntity(ctx,"loot","",Vec3(0)); Print(ctx,"owned");
    });
    StartEntityLifecycle(c); c.current_node="destroy-origin"; DestroyEntity(c,{"player"});
    Check("inline global/owned notification precedes deferred deletion and return",c.logs==std::vector<std::string>{"global:player","owned","global:sender"});
    Check("callback scopes restore Self and origin and preserve spawned entity",c.self=="player" && c.current_node=="destroy-origin" && FindEntitiesByName(c,"loot").size()==1);
    const auto checkpoint=EventCheckpoint(c);
    Ctx restored; LoadScene(restored,Snapshot(c)["scene"],SceneIdentityCheckpoint(c)); RestoreEventCheckpoint(restored,c,checkpoint);
    Check("destroyed listener identities restore without replaying removal",EventCheckpoint(restored)==checkpoint && restored.logs.empty());
    DestroyEntity(restored,{"inactive"}); Check("restored global pre-destruction callback remains live",restored.logs==std::vector<std::string>{"global:inactive"});
    auto bad=checkpoint;
    bad["queue"].push_back({{"event",1009},{"receiver",""},{"sender",""},{"args",{"inactive",true}},{"epoch",0},{"origin","forged"}});
    const auto before=EventCheckpoint(restored); const auto count=Alive(restored); const auto handle=restored.events;
    Failure([&]{RestoreEventCheckpoint(restored,c,bad);});
    Check("queued Destroyed payload rejects atomically",restored.events==handle && EventCheckpoint(restored)==before && Alive(restored)==count);
    Failure([&]{SendEvent(restored,1009,{},{},{EntityRef{"deleted"},true});});
    Failure([&]{BroadcastEvent(restored,1009,{},{EntityRef{"deleted"},true});});
    Check("native Send/Broadcast cannot queue before-destruction event",EventCheckpoint(restored)==before);
    Ctx failed; LoadScene(failed,Scene()); bool abort=true;
    BindEntityLifecycle(failed,1009,"abort",{"player"},[&abort](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>&) {
        if(abort) { DestroyEntity(ctx,{"sender"}); throw std::runtime_error("abort callback"); }
    });
    StartEntityLifecycle(failed);
    Failure([&]{DestroyEntity(failed,{"player"});});
    Check("callback error leaves deletion uncommitted and clears notification guard",EntityExists(failed,{"player"}) && EntityExists(failed,{"sender"}) && !DispatchingEntityDestroyed(failed));
    abort=false; DestroyEntity(failed,{"deleted"}); DestroyEntity(failed,{"player"});
    Check("callback error discards deferred edits and permits a later retry",EntityExists(failed,{"sender"}) && !EntityExists(failed,{"player"}));
    Ctx endless; LoadScene(endless,Scene());
    BindEntityLifecycle(endless,1009,"cascade",{},[](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>& args) {
        const auto child=SpawnEntity(ctx,"new child","",Vec3(0)); SetParent(ctx,child,std::get<EntityRef>(args.at(0)));
    });
    StartEntityLifecycle(endless); endless.remaining=20;
    const auto budget=Failure([&]{DestroyEntity(endless,{"player"});});
    Check("callback-created destruction cascade shares the budget and unwinds safely",budget.find("budget")!=std::string::npos && EntityExists(endless,{"player"}) && !DispatchingEntityDestroyed(endless));
    Ctx overflow; LoadScene(overflow,Scene());
    BindEntityLifecycle(overflow,1009,"overflow",{"player"},[](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>&) {
        for(int i=0;i<4097;++i) DestroyEntity(ctx,{"sender"});
    });
    StartEntityLifecycle(overflow); const auto limit=Failure([&]{DestroyEntity(overflow,{"player"});});
    DestroyEntity(overflow,{"deleted"});
    Check("deferred destructive edits are bounded and discarded after error",limit.find("4096")!=std::string::npos && EntityExists(overflow,{"player"}) && EntityExists(overflow,{"sender"}));
}
void CursorInput() {
    Ctx c; LoadScene(c,Scene());
    Check("cursor defaults are visible and unlocked",c.input.cursor_visible && !c.input.cursor_locked);
    AdvanceInput(c,{InputEvent::Position(10,20)});
    c.current_node="lock"; LockCursor(c,true); c.current_node="hide"; SetCursorVisible(c,false);
    AdvanceInput(c,{InputEvent::Motion(999,800,10000.25,-3000.5),InputEvent::Position(200,300)});
    Check("locked pointer keeps its anchor and continuous relative motion",MousePosition(c)==Vec3(10,20,0) && MouseDelta(c)==Vec3(10000.25,-3000.5,0));
    const auto saved=InputCheckpoint(c); Ctx candidate; RestoreInputCheckpoint(candidate,saved);
    Check("cursor request checkpoint preserves intent and originating node",InputCheckpoint(candidate)==saved && !candidate.input.cursor_visible && candidate.input.cursor_locked && candidate.input.cursor_node=="hide");
    for(int kind=0;kind<8;++kind) {
        auto bad=saved;
        if(kind==0) bad["cursor"]["visible"]=1;
        if(kind==1) bad["cursor"]["locked"]="true";
        if(kind==2) bad["cursor"]["node"]=7;
        if(kind==3) bad["cursor"]["extra"]=true;
        if(kind==4) bad["cursor"].erase("node");
        if(kind==5) bad.erase("cursor");
        if(kind==6) bad["version"]=2;
        if(kind==7) bad["cursor"]["node"]=std::string(MaxString+1,'x');
        Failure([&]{RestoreInputCheckpoint(candidate,bad);});
        Check("invalid cursor record rejects without changing input: "+std::to_string(kind),InputCheckpoint(candidate)==saved);
    }
    ClearInput(c);
    Check("Pause input clear retains cursor requests but clears relative impulses",c.input.cursor_locked && !c.input.cursor_visible && MouseDelta(c)==Vec3(0));
    LockCursor(c,false); AdvanceInput(c,{InputEvent::Position(30,40)});
    Check("unlock resumes absolute samples without changing requested visibility",MousePosition(c)==Vec3(30,40,0) && MouseDelta(c)==Vec3(0) && !c.input.cursor_visible);
    SetCursorVisible(c,true); Check("show cursor does not implicitly relock it",c.input.cursor_visible && !c.input.cursor_locked);
    auto legacy=saved; legacy["version"]=2; legacy.erase("cursor"); legacy.erase("gamepads"); legacy.erase("enabled_contexts"); legacy.erase("suppressed_actions"); RestoreInputCheckpoint(c,legacy);
    Check("version-2 pointer record upgrades with visible unlocked cursor",c.input.cursor_visible && !c.input.cursor_locked && c.input.cursor_node.empty() && MousePosition(c)==Vec3(10,20,0));
}
void PointerInput() {
    Ctx c; LoadScene(c,Scene());
    AdvanceInput(c,{InputEvent::Motion(10.25,-3.5,4.25,-2),InputEvent::Motion(12,4,1.75,7.5),
        InputEvent::Wheel(.25,2),InputEvent::Wheel(-.5,-.75)});
    const auto saved=InputCheckpoint(c);
    Check("pointer retains fractional position and accumulates two-dimensional motion/wheel",MousePosition(c)==Vec3(12,4,0) && MouseDelta(c)==Vec3(6,5.5,0) && MouseWheel(c)==Vec3(-.25,1.25,0));
    Check("repeated pointer reads do not consume per-frame state",MouseDelta(c)==MouseDelta(c) && MouseWheel(c)==MouseWheel(c) && InputCheckpoint(c)==saved);
    Ctx restored; RestoreInputCheckpoint(restored,saved);
    Check("pointer checkpoint restores position and same-frame transient values",InputCheckpoint(restored)==saved);
    for(int kind=0;kind<7;++kind) {
        auto bad=saved;
        if(kind==0) bad["pointer"]["position"]={1,2,3};
        if(kind==1) bad["pointer"]["delta"]={true,0};
        if(kind==2) bad["pointer"]["wheel"]={nullptr,0};
        if(kind==3) bad["pointer"]["extra"]=0;
        if(kind==4) bad["pointer"].erase("position");
        if(kind==5) bad["pointer"]["wheel"]={std::numeric_limits<double>::infinity(),0};
        if(kind==6) bad["version"]=true;
        Failure([&]{RestoreInputCheckpoint(c,bad);});
        Check("invalid pointer checkpoint leaves input unchanged: "+std::to_string(kind),InputCheckpoint(c)==saved);
    }
    Failure([&]{AdvanceInput(c,{{"A",true},InputEvent::Motion(0,0,std::numeric_limits<double>::infinity(),0)});});
    Check("invalid motion rejects before applying keys or clearing previous edges",InputCheckpoint(c)==saved);
    Failure([&]{AdvanceInput(c,{InputEvent::Wheel(1e308,0),InputEvent::Wheel(1e308,0)});});
    Check("pointer accumulation overflow rejects before mutation",InputCheckpoint(c)==saved);
    AdvanceInput(c,{});
    Check("empty frame retains absolute position but clears delta and wheel",MousePosition(c)==Vec3(12,4,0) && MouseDelta(c)==Vec3(0) && MouseWheel(c)==Vec3(0));
    AdvanceInput(c,{InputEvent::Motion(30,40,18,36),InputEvent::Wheel(0,3),{},InputEvent::Motion(31,42,1,2)});
    Check("release-all discards earlier pointer impulses and retains later ordered motion",MousePosition(c)==Vec3(31,42,0) && MouseDelta(c)==Vec3(1,2,0) && MouseWheel(c)==Vec3(0));
    ClearInput(c);
    Check("Pause clear keeps position without replaying transient pointer input",MousePosition(c)==Vec3(31,42,0) && MouseDelta(c)==Vec3(0) && MouseWheel(c)==Vec3(0));
    auto legacy=saved; legacy["version"]=1; legacy.erase("pointer"); legacy.erase("cursor"); legacy.erase("gamepads"); legacy.erase("enabled_contexts"); legacy.erase("suppressed_actions"); RestoreInputCheckpoint(c,legacy);
    Check("legacy input checkpoint upgrades with neutral pointer state",MousePosition(c)==Vec3(0) && MouseDelta(c)==Vec3(0) && MouseWheel(c)==Vec3(0));
    Json replay={{"version",2},{"events",{{{"frame",0u},{"type","motion"},{"x",1.25},{"y",2},{"dx",.25},{"dy",-.5}},
        {{"frame",0u},{"type","wheel"},{"x",-.25},{"y",1.5}},{{"frame",1u},{"type","position"},{"x",40},{"y",50}}}}};
    const auto inputs=LoadInputReplay(replay); AdvanceInput(c,inputs.at(0)); AdvanceInput(c,inputs.at(1));
    Check("version-2 replay reads motion, wheel and position without phantom displacement",MousePosition(c)==Vec3(40,50,0) && MouseDelta(c)==Vec3(0) && MouseWheel(c)==Vec3(0));
    for(int kind=0;kind<6;++kind) {
        auto bad=replay;
        if(kind==0) bad["version"]=1;
        if(kind==1) bad["events"][0]["x"]=true;
        if(kind==2) bad["events"][0].erase("dx");
        if(kind==3) bad["events"][1]["z"]=0;
        if(kind==4) bad["events"][1]["type"]="unknown";
        if(kind==5) bad["events"][0]["dx"]=std::numeric_limits<double>::quiet_NaN();
        Failure([&]{LoadInputReplay(bad);});
        Check("malformed/legacy pointer replay rejects: "+std::to_string(kind),true);
    }
}
void InputEvents() {
    auto scene=Scene(); scene["input"]={{"version",1},{"actions",{{"jump",{"Space","MouseLeft"}}}},{"axes",Json::object()}};
    Ctx c; LoadScene(c,scene);
    for(int type=10008;type<=10012;++type) BindInputEvent(c,type,"input"+std::to_string(type),"",
        [type](Ctx& ctx,EntityRef sender,EntityRef receiver,const std::vector<Value>& args) {
            Require(sender.id.empty() && receiver.id.empty() && ctx.self.empty(),"Input is global");
            Print(ctx,std::to_string(type)+":"+std::get<std::string>(args.at(0))+":"+(std::get<bool>(args.at(1)) ? "down" : "up"));
        });
    for(const auto& bad:std::vector<std::pair<int,std::string>>{{10008,"MouseLeft"},{10010,"Space"},{10011,"missing"},{9999,""}}) {
        const auto before=EventCheckpoint(c); const auto alive=Alive(c);
        Failure([&]{BindInputEvent(c,bad.first,"invalid",bad.second,[](Ctx&,EntityRef,EntityRef,const std::vector<Value>&){});});
        Check("invalid input filter/ID leaves event bindings unchanged: "+std::to_string(bad.first),EventCheckpoint(c)==before && Alive(c)==alive);
    }
    AdvanceInput(c,{{"Space",true},{"MouseLeft",true},{"Space",false},{"MouseLeft",false},{"Space",true},{"Space",false}});
    auto saved=EventCheckpoint(c); auto input=InputCheckpoint(c);
    Ctx restored; LoadScene(restored,scene); RestoreInputCheckpoint(restored,input); RestoreEventCheckpoint(restored,c,saved);
    Check("ordered input queue and filtered listener identities roundtrip",EventCheckpoint(restored)==saved && InputCheckpoint(restored)==input && saved["queue"].size()==10);
    for(int kind=0;kind<6;++kind) {
        auto bad=saved;
        if(kind==0) bad["queue"][0]["args"][0]="MouseLeft";
        if(kind==1) bad["queue"][0]["args"][1]=false;
        if(kind==2) bad["queue"][0]["sender"]="player";
        if(kind==3) bad["subscriptions"][0]["enabled"]=false;
        if(kind==4) bad["bindings"]["events"][0]["listeners"][0]["filter"]="Space";
        if(kind==5) bad["queue"][1]["args"][0]="unknown-action";
        const auto before=EventCheckpoint(restored); const auto alive=Alive(restored); const auto handle=restored.events;
        Failure([&]{RestoreEventCheckpoint(restored,c,bad);});
        Check("invalid input checkpoint rejects atomically: "+std::to_string(kind),restored.events==handle && EventCheckpoint(restored)==before && Alive(restored)==alive);
    }
    DrainEvents(c); DrainEvents(restored);
    Check("restored input transitions retain original order and global scope",c.logs==restored.logs && c.logs.size()==10 && c.logs.front()=="10008:Space:down" && c.logs.back()=="10012:jump:up");
    AdvanceInput(c,{}); DrainEvents(c);
    Check("clearing input edges does not replay transitions",c.logs.size()==10);
    AdvanceInput(c,{{"Space",true}}); ClearInput(c); DrainEvents(c);
    Check("Pause/Stop input clear drops queued callbacks without synthetic release",c.logs.size()==10 && c.keys.empty() && EventCheckpoint(c)["queue"].empty());
    const auto neutral=InputCheckpoint(c);
    Failure([&]{AdvanceInput(c,{{"A",true},{"Unknown",true}});});
    Check("invalid raw input rejects before changing held state or queuing callbacks",InputCheckpoint(c)==neutral && EventCheckpoint(c)["queue"].empty());
    Ctx overflow; LoadScene(overflow,scene); BindInputEvent(overflow,10008,"input-budget","",[](Ctx&,EntityRef,EntityRef,const std::vector<Value>&){});
    std::vector<InputEvent> many; for(int i=0;i<4097;++i) {many.push_back({"Space",true});many.push_back({"Space",false});}
    const auto failure=Failure([&]{AdvanceInput(overflow,many);});
    Check("input delivery queue is bounded with matching graph origin",failure.find("4096")!=std::string::npos && overflow.current_node=="input-budget");
}
}
int main(int argc,char** argv) {
    try {
        if(argc==2 && std::string(argv[1])=="--self-test") { Malformed(); Boundaries(); Budget(); Prefab(); ClockDomains(); AnimationEvents(); EntityLifecycleEvents(); PhysicsPrefabLifecycle(); DestroyedEvents(); InputEvents(); PointerInput(); CursorInput(); }
        else if(argc==3 && std::string(argv[1])=="--write") {
            auto c=Initial(); Json file={{"scene",Snapshot(c)["scene"]},{"events",EventCheckpoint(c)}};
            file["trace"]=Continue(c);
            std::ofstream out(std::filesystem::u8path(argv[2]),std::ios::binary); out << file.dump(); out.close();
            Check("write checkpoint and uninterrupted reference trace",bool(out));
        } else if(argc==3 && std::string(argv[1])=="--read") {
            std::ifstream input(std::filesystem::u8path(argv[2]),std::ios::binary); Json file; input >> file;
            Ctx program; LoadScene(program,Scene()); BindProgram(program);
            Ctx c; LoadScene(c,file.at("scene")); RestoreEventCheckpoint(c,program,file.at("events"));
            Check("fresh-process checkpoint roundtrip",EventCheckpoint(c)==file.at("events"));
            Check("fresh-process 160-frame continuation matches reference",Continue(c)==file.at("trace"));
        } else throw std::runtime_error("Usage: node_event_probe --self-test | --write FILE | --read FILE");
        std::cout << Json({{"passed",true},{"checks",checks}}).dump() << '\n'; return 0;
    } catch(const std::exception& e) {
        std::cerr << e.what() << '\n'; std::cout << Json({{"passed",false},{"checks",checks},{"error",e.what()}}).dump() << '\n'; return 1;
    }
}
