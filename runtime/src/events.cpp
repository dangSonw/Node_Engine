#include "runtime.hpp"
#include <flecs.h>
#include <exception>
#include <queue>
#include <tuple>
#include <deque>
#include <iomanip>
#include <locale>
#include <sstream>
#include <array>

namespace rt {
namespace {
bool IsEntityLifecycle(std::int64_t event) { return event>=1006 && event<=1009; }
using Key = std::pair<std::string, std::string>; // owner, name
struct Timer {
    long double deadline, interval, remaining = 0;
    bool repeat, paused = false;
    std::uint64_t serial;
    std::string origin;
    bool suspended = false;
    bool unscaled = false;
};
struct Listener { std::string node, filter; TimerHandler callback; };
struct Receiver { ecs_entity_t entity=0, observer=0; std::vector<Listener> listeners; bool active=true; std::uint64_t epoch=0; };
struct Delivery {
    Ctx& ctx;
    const std::string& name;
    EntityRef owner;
    std::exception_ptr error;
    std::vector<Listener> listeners;
};
struct EventScope {
    Ctx& c;
    std::string self;
    decltype(Ctx::locals) locals;
    explicit EventScope(Ctx& c):c(c),self(c.self),locals(std::move(c.locals)) { c.locals.clear(); }
    ~EventScope() { c.self=std::move(self); c.locals=std::move(locals); }
};
struct EventListener { std::string node; EventHandler callback; std::string filter; };
struct Subscription {
    ecs_entity_t entity=0;
    ecs_entity_t observer=0;
    bool enabled;
    std::uint64_t epoch = 0;
    std::vector<EventListener> listeners;
    bool active=true;
    std::uint64_t activity_epoch=0;
};
struct EventType { ecs_entity_t entity; std::vector<std::string> types; };
using EventKey = std::pair<int,std::string>;
struct Envelope {
    EventKey target;
    EntityRef sender;
    std::shared_ptr<const std::vector<Value>> args;
    std::uint64_t epoch;
    std::string origin;
    std::size_t bytes;
};
struct CustomDelivery { Ctx& ctx; const Envelope& envelope; std::exception_ptr error; std::vector<EventListener> listeners; };
void OnCustom(ecs_iter_t* it) noexcept {
    auto& delivery=*static_cast<CustomDelivery*>(it->param);
    const auto& subscription=*static_cast<Subscription*>(it->ctx);
    try { delivery.listeners=subscription.listeners; }
    catch(...) { delivery.error=std::current_exception(); }
}
// Never unwind a C++ exception across Flecs' C callback boundary.
void OnTimer(ecs_iter_t* it) noexcept {
    auto& delivery = *static_cast<Delivery*>(it->param);
    auto& receiver = *static_cast<Receiver*>(it->ctx);
    try { delivery.listeners=receiver.listeners; }
    catch(...) { delivery.error = std::current_exception(); }
}
}
struct EventSystem {
    std::shared_ptr<SceneWorld> scene;
    ecs_world_t* world;
    ecs_entity_t timer_event = 0;
    std::map<std::string, Receiver> receivers;
    std::vector<ecs_entity_t> observers;
    std::map<int,EventType> types;
    std::map<EventKey,Subscription> subscriptions;
    std::deque<Envelope> queue;
    std::size_t queued_bytes=0;
    // Only cancels listeners in a currently dispatched action; queued deliveries are removed.
    std::map<std::string,std::uint64_t> input_epochs;
    bool draining=false, advancing=false;
    bool lifecycle_started=false;
    bool notifying_destruction=false;
    std::map<std::string,bool> lifecycle_entities;
    std::map<Key, Timer> timers;
    long double clock = 0, unscaled_clock = 0;
    long double TimerClock(const Timer& timer) const { return timer.unscaled ? unscaled_clock : clock; }
    std::uint64_t serial = 0;
    explicit EventSystem(Ctx& c):scene(c.world),world(NativeWorld(c)) {
        timer_event = ecs_new(world);
    }
    ~EventSystem() {
        for(auto observer:observers) if(ecs_is_alive(world,observer)) ecs_delete(world,observer);
        for(const auto& [id,type]:types) if(ecs_is_alive(world,type.entity)) ecs_delete(world,type.entity);
        if(timer_event && ecs_is_alive(world,timer_event)) ecs_delete(world,timer_event);
    }
    EventSystem(const EventSystem&) = delete;
    EventSystem& operator=(const EventSystem&) = delete;
};
std::shared_ptr<EventSystem> CreateEventSystem(Ctx& c) { return std::make_shared<EventSystem>(c); }
static EventSystem& System(Ctx& c) {
    if(!c.events) c.events = CreateEventSystem(c);
    return *c.events;
}
static void Owner(Ctx& c, const EntityRef& owner) {
    if(!owner.id.empty()) NativeEntity(c, owner.id);
}
static bool OwnerActive(const Ctx& c,const std::string& owner) {
    return owner.empty() || IsEntityActive(c,{owner});
}
static bool ReceiverActive(const Ctx& c,const EventKey& key) {
    return key.second.empty() || (IsEntityLifecycle(key.first) ? EntityExists(c,{key.second}) : OwnerActive(c,key.second));
}
static void RefreshEntityLifecycle(Ctx&);
void RefreshEntityActivity(Ctx& c) {
    if(!c.events) return;
    auto& system=*c.events;
    for(auto& [key,timer]:system.timers) {
        const bool suspended=!OwnerActive(c,key.first);
        if(timer.suspended==suspended) continue;
        if(!timer.paused) {
            if(suspended) timer.remaining=std::max(0.L,timer.deadline-system.TimerClock(timer));
            else timer.deadline=system.TimerClock(timer)+timer.remaining;
        }
        timer.suspended=suspended;
        timer.serial=++system.serial; // Old due batches cannot run after a toggle.
    }
    for(auto& [owner,receiver]:system.receivers) {
        const bool active=OwnerActive(c,owner);
        if(receiver.active!=active) { receiver.active=active; ++receiver.epoch; }
    }
    for(auto& [key,subscription]:system.subscriptions) {
        const bool active=ReceiverActive(c,key);
        if(subscription.active!=active) { subscription.active=active; ++subscription.epoch; ++subscription.activity_epoch; }
    }
    RefreshEntityLifecycle(c);
}
static Key TimerKey(Ctx& c, const std::string& name, const EntityRef& owner) {
    VariableName(name);
    Owner(c, owner);
    return {owner.id, name};
}
void BindTimer(Ctx& c, std::string node, EntityRef owner, std::string filter, TimerHandler callback) {
    Owner(c, owner);
    if(!filter.empty()) VariableName(filter);
    auto& system = System(c);
    auto [found, inserted] = system.receivers.try_emplace(owner.id);
    auto& receiver = found->second;
    if(inserted) {
        receiver.entity = NativeEntity(c,owner.id);
        receiver.active = OwnerActive(c,owner.id);
        ecs_observer_desc_t observer{};
        observer.query.terms[0].id = EcsAny;
        observer.query.terms[0].src.id = receiver.entity;
        observer.events[0] = system.timer_event;
        observer.callback = OnTimer;
        observer.ctx = &receiver;
        auto handle=ecs_observer_init(system.world,&observer);
        if(!handle) throw std::runtime_error("Cannot register Flecs timer observer");
        receiver.observer=handle;
        system.observers.push_back(handle);
    }
    receiver.listeners.push_back({std::move(node), std::move(filter), std::move(callback)});
    std::sort(receiver.listeners.begin(), receiver.listeners.end(), [](const Listener& a, const Listener& b) { return a.node < b.node; });
}
void StartTimer(Ctx& c, std::string name, double seconds, bool repeat, EntityRef owner, bool unscaled) {
    const auto key = TimerKey(c, name, owner);
    if(!std::isfinite(seconds) || seconds < 0 || (repeat && seconds == 0))
        throw std::runtime_error("Timer duration must be finite and nonnegative; repeating duration must be positive");
    auto& system = System(c);
    const auto clock = unscaled ? system.unscaled_clock : system.clock;
    const auto deadline = clock + seconds;
    finite(static_cast<double>(deadline));
    if(seconds > 0 && deadline <= clock) throw std::runtime_error("Timer duration is too small at the current timer clock");
    if(!system.timers.contains(key) && system.timers.size() >= 4096) throw std::runtime_error("At most 4096 active timers are allowed");
    system.timers.insert_or_assign(key, Timer{deadline, seconds, seconds, repeat, false, ++system.serial, c.current_node, !OwnerActive(c,owner.id), unscaled});
}
void StopTimer(Ctx& c, std::string name, EntityRef owner) { System(c).timers.erase(TimerKey(c, name, owner)); }
void PauseTimer(Ctx& c, std::string name, EntityRef owner) {
    const auto key = TimerKey(c, name, owner);
    auto& system = System(c);
    auto found = system.timers.find(key);
    if(found != system.timers.end() && !found->second.paused) {
        auto& timer = found->second;
        if(!timer.suspended) timer.remaining = std::max(0.L, timer.deadline - system.TimerClock(timer));
        timer.paused = true;
    }
}
void ResumeTimer(Ctx& c, std::string name, EntityRef owner) {
    const auto key = TimerKey(c, name, owner);
    auto& system = System(c);
    auto found = system.timers.find(key);
    if(found != system.timers.end() && found->second.paused) {
        auto& timer = found->second;
        auto deadline = system.TimerClock(timer) + timer.remaining;
        finite(static_cast<double>(deadline));
        timer.deadline = deadline;
        timer.paused = false;
        timer.serial = ++system.serial;
    }
}
bool TimerExists(Ctx& c, std::string name, EntityRef owner) { return System(c).timers.contains(TimerKey(c, name, owner)); }
bool IsTimerPaused(Ctx& c, std::string name, EntityRef owner) {
    auto& system = System(c);
    auto found = system.timers.find(TimerKey(c, name, owner));
    return found != system.timers.end() && found->second.paused;
}
double TimerRemaining(Ctx& c, std::string name, EntityRef owner) {
    auto& system = System(c);
    auto found = system.timers.find(TimerKey(c, name, owner));
    if(found == system.timers.end()) return 0;
    const auto& timer = found->second;
    return static_cast<double>((timer.paused || timer.suspended) ? timer.remaining : std::max(0.L, timer.deadline - system.TimerClock(timer)));
}
void AdvanceTimers(Ctx& c) {
    auto& system = System(c);
    if(system.advancing) throw std::runtime_error("Timer advancement is already in progress");
    struct Guard { bool& advancing; ~Guard(){advancing=false;} } guard{system.advancing};
    system.advancing=true;
    if(!std::isfinite(c.dt) || c.dt < 0 || !std::isfinite(c.unscaled_dt) || c.unscaled_dt < 0)
        throw std::runtime_error("Invalid timer delta time");
    const std::array<long double,2> starts{system.clock,system.unscaled_clock};
    const std::array<long double,2> steps{c.time_frozen ? 0.L : c.dt,c.unscaled_dt};
    const auto next=system.clock+steps[0], next_unscaled=system.unscaled_clock+steps[1];
    finite(static_cast<double>(next)); finite(static_cast<double>(next_unscaled));
    system.clock=next; system.unscaled_clock=next_unscaled;
    using Pending = std::tuple<long double, std::uint64_t, Key>;
    std::priority_queue<Pending, std::vector<Pending>, std::greater<Pending>> pending;
    auto due = [&](const Timer& timer) {
        return (timer.unscaled || !c.time_frozen) && static_cast<double>(timer.deadline) <= static_cast<double>(system.TimerClock(timer));
    };
    // Compare expiration positions within this frame, never unrelated absolute clocks.
    auto enqueue = [&](const Key& key,const Timer& timer) {
        const auto step=steps[timer.unscaled];
        const auto position=step>0 ? (timer.deadline-starts[timer.unscaled])/step : 0.L;
        pending.emplace(position,timer.serial,key);
    };
    for(const auto& [key, timer] : system.timers)
        if(!timer.paused && !timer.suspended && due(timer)) enqueue(key,timer);
    // Timers created/restarted/resumed in a callback enter the next frame's batch.
    while(!pending.empty()) {
        const auto [position, serial, key] = pending.top(); pending.pop();
        auto found = system.timers.find(key);
        if(found == system.timers.end() || found->second.serial != serial || found->second.paused || found->second.suspended) continue;
        auto& timer = found->second;
        const auto deadline=timer.deadline;
        Tick(c, timer.origin); // Also bounds repeats with no listeners.
        if(timer.repeat) {
            const auto next_deadline = deadline + timer.interval;
            if(next_deadline <= deadline || !std::isfinite(static_cast<double>(next_deadline)))
                throw std::runtime_error("Repeating timer deadline cannot advance");
            timer.deadline = next_deadline;
            if(due(timer)) enqueue(key,timer);
        } else system.timers.erase(found); // A one-shot is already inactive inside its callback.
        auto receiver = system.receivers.find(key.first);
        if(receiver == system.receivers.end()) continue;
        const auto epoch=receiver->second.epoch;
        Delivery delivery{c, key.second, EntityRef{key.first}, {}, {}};
        ecs_event_desc_t event{};
        event.event = system.timer_event;
        event.entity = receiver->second.entity;
        event.param = &delivery;
        ecs_emit(system.world, &event);
        if(delivery.error) std::rethrow_exception(delivery.error);
        // User graphs run outside Flecs' observer defer scope. Newly created
        // components are readable immediately, and deleting a receiver cannot
        // invalidate an active Flecs observer iterator.
        for(const auto& listener:delivery.listeners) {
            if(!listener.filter.empty() && listener.filter!=delivery.name) continue;
            if(!OwnerActive(c,delivery.owner.id) || receiver->second.epoch!=epoch) break;
            EventScope scope(c); c.self=delivery.owner.id;
            Tick(c,listener.node);
            listener.callback(c,delivery.name,delivery.owner);
        }
    }
}
Json TimerSnapshot(const Ctx& c) {
    Json result = Json::array();
    if(c.events) for(const auto& [key, timer] : c.events->timers) {
        result.push_back({{"owner", key.first}, {"name", key.second}, {"repeat", timer.repeat}, {"paused", timer.paused},
            {"duration", static_cast<double>(timer.interval)},
            {"remaining", static_cast<double>((timer.paused || timer.suspended) ? timer.remaining : std::max(0.L, timer.deadline - c.events->TimerClock(timer)))}});
        if(timer.suspended) result.back()["suspended"]=true;
        if(timer.unscaled) result.back()["unscaled"]=true;
    }
    return result;
}
void BindInterpretedEvents(Ctx& c, const Json& ir) {
    ConfigureContinuations(c,ir);
    std::map<int,std::vector<std::string>> parameters;
    for(const auto& definition:ir.value("event_definitions",Json::array())) {
        int id=definition.at("id").get<int>();
        std::vector<std::string> types;
        for(const auto& p:definition.at("parameters")) {
            types.push_back(p.at("type").get<std::string>());
            parameters[id].push_back(p.at("name").get<std::string>());
        }
        DeclareEvent(c,id,std::move(types));
    }
    for(const auto& handler:ir.at("events").value("custom",Json::array())) {
        const auto node=handler.at("node").get<std::string>();
        const auto id=handler.at("event").get<int>();
        BindEvent(c,id,node,EntityRef{handler.at("owner").get<std::string>()},handler.at("enabled").get<bool>(),
            [node,names=parameters[id],body=handler.at("body")](Ctx& ctx,EntityRef sender,EntityRef receiver,const std::vector<Value>& args) {
                ctx.locals[{node,"Sender"}]=std::move(sender);
                ctx.locals[{node,"Receiver"}]=std::move(receiver);
                for(std::size_t i=0;i<names.size();++i) ctx.locals[{node,names[i]}]=args.at(i);
                Execute(ctx,body);
            });
    }
    for(const auto& handler:ir.at("events").value("persistence",Json::array())) {
        const auto node=handler.at("node").get<std::string>();
        BindGameSaveEvent(c,handler.at("event").get<int>(),node,
            [node,body=handler.at("body")](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>& args) {
                ctx.locals[{node,"Slot"}]=args.at(0);
                ctx.locals[{node,"Error"}]=args.at(1);
                Execute(ctx,body);
            });
    }
    for(const auto& handler:ir.at("events").value("world_pause",Json::array())) {
        BindWorldPauseEvent(c,handler.at("event").get<int>(),handler.at("node").get<std::string>(),
            [body=handler.at("body")](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>&) { Execute(ctx,body); });
    }
    for(const auto& handler:ir.at("events").value("scene_failure",Json::array())) {
        const auto node=handler.at("node").get<std::string>();
        BindSceneLoadFailed(c,node,[node,body=handler.at("body")](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>& args) {
            ctx.locals[{node,"Scene"}]=args.at(0); ctx.locals[{node,"Error"}]=args.at(1); Execute(ctx,body);
        });
    }
    for(const auto& handler:ir.at("events").value("physics",Json::array())) {
        const auto node=handler.at("node").get<std::string>();
        BindPhysicsEvent(c,handler.at("event").get<int>(),node,{handler.at("owner").get<std::string>()},
            [node,body=handler.at("body")](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>& args) {
                const std::array<const char*,4> names={"Entity","Other","Point","Normal"};
                for(std::size_t i=0;i<names.size();++i) ctx.locals[{node,names[i]}]=args.at(i);
                Execute(ctx,body);
            });
    }
    for(const auto& handler:ir.at("events").value("input",Json::array())) {
        const auto node=handler.at("node").get<std::string>();
        const auto event=handler.at("event").get<int>();
        const std::string port=event==10008 || event==10009 ? "Key" : event==10010 || event==10020 ? "Button" : "Action";
        BindInputEvent(c,event,node,handler.at("filter").get<std::string>(),
            [node,port,body=handler.at("body")](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>& args) {
                ctx.locals[{node,port}]=args.at(0);
                ctx.locals[{node,"Down"}]=args.at(1);
                if(args.size()==3) ctx.locals[{node,"Controller"}]=args.at(2);
                Execute(ctx,body);
            });
    }
    for(const auto& handler:ir.at("events").value("entity_lifecycle",Json::array())) {
        const auto node=handler.at("node").get<std::string>();
        BindEntityLifecycle(c,handler.at("event").get<int>(),node,{handler.at("owner").get<std::string>()},
            [node,body=handler.at("body")](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>& args) {
                ctx.locals[{node,"Entity"}]=args.at(0);
                ctx.locals[{node,"Active"}]=args.at(1);
                Execute(ctx,body);
            });
    }
    for(const auto& handler:ir.at("events").value("animation_finished",Json::array())) {
        const auto node=handler.at("node").get<std::string>();
        BindAnimationFinished(c,node,{handler.at("owner").get<std::string>()},handler.at("filter").get<std::string>(),
            [node,body=handler.at("body")](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>& args) {
                ctx.locals[{node,"Entity"}]=args.at(0);
                ctx.locals[{node,"Clip"}]=args.at(1);
                Execute(ctx,body);
            });
    }
    for(const auto& handler:ir.at("events").value("animation_notify",Json::array())) {
        const auto node=handler.at("node").get<std::string>();
        BindAnimationNotify(c,node,{handler.at("owner").get<std::string>()},handler.at("filter").get<std::string>(),
            [node,body=handler.at("body")](Ctx& ctx,EntityRef,EntityRef,const std::vector<Value>& args) {
                ctx.locals[{node,"Entity"}]=args.at(0);
                ctx.locals[{node,"Notify"}]=args.at(1);
                Execute(ctx,body);
            });
    }
    for(const auto& handler:ir.at("events").value("ui",Json::array())) {
        const auto node=handler.at("node").get<std::string>();
        BindUiEvent(c,node,handler.at("kind"),handler.at("widget"),handler.at("element"),
            [node,body=handler.at("body")](Ctx& ctx,const UiEvent& event) {
                ctx.locals[{node,"Widget"}]=event.document;
                ctx.locals[{node,"Element"}]=event.element;
                ctx.locals[{node,"Value"}]=event.value;
                ctx.locals[{node,"Checked"}]=event.checked;
                Execute(ctx,body);
            });
    }
    for(const auto& handler : ir.at("events").value("timers", Json::array())) {
        const auto node = handler.at("node").get<std::string>();
        BindTimer(c, node, EntityRef{handler.at("owner").get<std::string>()}, handler.at("filter").get<std::string>(),
            [node, body=handler.at("body")](Ctx& ctx, const std::string& name, EntityRef owner) {
                ctx.locals[{node, "Name"}] = name;
                ctx.locals[{node, "Owner"}] = std::move(owner);
                Execute(ctx, body);
            });
    }
}
static bool IsGameSaveEvent(std::int64_t event) { return event>=23101 && event<=23104; }
static bool IsSceneFailure(std::int64_t event) {return event==1020;}
static bool IsWorldPauseEvent(std::int64_t event) { return event==1017 || event==1018; }
static bool IsPhysicsEvent(std::int64_t event) { return event>=1011 && event<=1016; }
static bool IsAnimationFinishedEvent(std::int64_t event) { return event==13014; }
static bool IsAnimationNotifyEvent(std::int64_t event) { return event==13016; }
static bool IsInputEvent(std::int64_t event) { return (event>=10008 && event<=10012) || event==10020; }
static bool InputEventName(const Ctx& c,int event,const std::string& name) {
    return event==10020 ? IsGamepadButton(name) : event>=10011 ? c.input.actions.contains(name) : IsInputButton(name) && name.starts_with("Mouse")== (event==10010);
}
static bool IsBuiltinEvent(std::int64_t event) { return IsSceneFailure(event)||IsWorldPauseEvent(event)||IsGameSaveEvent(event)||IsPhysicsEvent(event)||IsAnimationFinishedEvent(event)||IsAnimationNotifyEvent(event)||IsEntityLifecycle(event)||IsInputEvent(event); }
static void BindEventListener(Ctx&,int,EntityRef,bool,EventListener);
static void DeclareEventType(Ctx& c, int event, std::vector<std::string> types) {
    auto& system=System(c);
    const auto custom_count=std::count_if(system.types.begin(),system.types.end(),[](const auto& t){ return !IsBuiltinEvent(t.first); });
    if((!IsBuiltinEvent(event) && (event<100000 || event>199999 || custom_count>=256)) ||
       types.size()>32 || system.types.contains(event) ||
       (IsGameSaveEvent(event) && types!=std::vector<std::string>{"string","string"}) ||
       (IsWorldPauseEvent(event) && !types.empty()) ||
       (IsSceneFailure(event) && types!=std::vector<std::string>{"string","string"}) ||
       (IsPhysicsEvent(event) && types!=std::vector<std::string>{"entity","entity","vec3","vec3"}) ||
       ((IsAnimationFinishedEvent(event) || IsAnimationNotifyEvent(event)) && types!=std::vector<std::string>{"entity","string"}) ||
       (IsInputEvent(event) && types!=(event==10020 ? std::vector<std::string>{"string","bool","int"} : std::vector<std::string>{"string","bool"})) ||
       (IsEntityLifecycle(event) && types!=std::vector<std::string>{"entity","bool"}))
        throw std::runtime_error("Invalid or duplicate event definition");
    // Reject corrupted IR metadata before creating an observer or a queue entry.
    for(const auto& type:types) {
        bool valid=false;
        for(const std::string scalar:{"float","int","bool","string","vec2","vec3","vec4","quat","mat4","entity"})
            valid |= type==scalar || type=="array<"+scalar+">" || type=="map<"+scalar+">" || type=="set<"+scalar+">";
        for(const auto& group:{std::string("structs"),std::string("enums")})
            for(const auto& definition:c.user_types.at(group)) {
                const auto nominal=(group=="structs" ? "struct:" : "enum:")+definition.at("name").get<std::string>();
                valid |= type==nominal || type=="array<"+nominal+">" || type=="map<"+nominal+">" || type=="set<"+nominal+">";
            }
        if(!valid) throw std::runtime_error("Unsupported event payload type: "+type);
    }
    system.types.emplace(event,EventType{ecs_new(system.world),std::move(types)});
}
void DeclareEvent(Ctx& c, int event, std::vector<std::string> types) {
    if(event<100000 || event>199999) throw std::runtime_error("Invalid custom event ID");
    DeclareEventType(c,event,std::move(types));
}
void BindGameSaveEvent(Ctx& c, int event, std::string node, EventHandler callback) {
    if(!IsGameSaveEvent(event)) throw std::runtime_error("Invalid game persistence event ID");
    if(!System(c).types.contains(event)) DeclareEventType(c,event,{"string","string"});
    BindEvent(c,event,std::move(node),EntityRef{},true,std::move(callback));
}
void QueueGameSaveEvent(Ctx& c, bool load, bool success, std::string slot, std::string error) {
    const int event=23101+(load ? 2 : 0)+(success ? 0 : 1);
    if(c.events && c.events->types.contains(event))
        BroadcastEvent(c,event,EntityRef{},{std::move(slot),std::move(error)});
}
void BindWorldPauseEvent(Ctx& c,int event,std::string node,EventHandler callback) {
    if(!IsWorldPauseEvent(event)) throw std::runtime_error("Invalid world pause event ID");
    if(!System(c).types.contains(event)) DeclareEventType(c,event,{});
    BindEvent(c,event,std::move(node),{},true,std::move(callback));
}
void QueueWorldPauseEvent(Ctx& c,bool paused) {
    const int event=paused ? 1017 : 1018;
    if(c.events && c.events->types.contains(event)) BroadcastEvent(c,event,{},{});
}
void BindSceneLoadFailed(Ctx& c,std::string node,EventHandler callback) {
    if(!System(c).types.contains(1020)) DeclareEventType(c,1020,{"string","string"});
    BindEvent(c,1020,std::move(node),{},true,std::move(callback));
}
void QueueSceneLoadFailed(Ctx& c,std::string scene,std::string error) {
    if(c.events && c.events->types.contains(1020)) BroadcastEvent(c,1020,{},{std::move(scene),std::move(error)});
}
void BindPhysicsEvent(Ctx& c,int event,std::string node,EntityRef receiver,EventHandler callback) {
    if(!IsPhysicsEvent(event)) throw std::runtime_error("Invalid physics event ID");
    if(!System(c).types.contains(event)) DeclareEventType(c,event,{"entity","entity","vec3","vec3"});
    BindEvent(c,event,std::move(node),std::move(receiver),true,std::move(callback));
}
void QueuePhysicsContact(Ctx& c,const PhysicsContact& contact) {
    const int phase=contact.phase=="enter"?0:contact.phase=="stay"?1:contact.phase=="exit"?2:-1;
    if(phase<0) throw std::runtime_error("Invalid physics contact phase");
    const int event=1011+(contact.sensor?3:0)+phase;
    if(!c.events || !c.events->types.contains(event)) return;
    const EntityRef first{contact.first},second{contact.second};
    // Exit payloads can refer to a removed body/entity; the sender is global.
    SendEvent(c,event,EntityRef{},EntityRef{},{first,second,contact.point,contact.normal});
    if(EntityExists(c,first)) SendEvent(c,event,first,EntityRef{},{first,second,contact.point,contact.normal});
    if(EntityExists(c,second)) SendEvent(c,event,second,EntityRef{},{second,first,contact.point,Vec3(-contact.normal)});
}
void BindAnimationFinished(Ctx& c,std::string node,EntityRef receiver,std::string clip_filter,EventHandler callback) {
    if(clip_filter.size()>512 || clip_filter.find('\0')!=std::string::npos)
        throw std::runtime_error("Animation clip filter must be at most 512 UTF-8 bytes with no NUL");
    if(!System(c).types.contains(13014)) DeclareEventType(c,13014,{"entity","string"});
    BindEventListener(c,13014,std::move(receiver),true,{std::move(node),std::move(callback),std::move(clip_filter)});
}
void QueueAnimationFinished(Ctx& c,EntityRef entity,std::string clip) {
    if(!c.events || !c.events->types.contains(13014)) return;
    SendEvent(c,13014,{},EntityRef{},{entity,clip});
    if(EntityExists(c,entity)) SendEvent(c,13014,entity,EntityRef{},{entity,std::move(clip)});
}
void BindAnimationNotify(Ctx& c,std::string node,EntityRef receiver,std::string notify_filter,EventHandler callback) {
    if(notify_filter.size()>512 || notify_filter.find('\0')!=std::string::npos)
        throw std::runtime_error("Animation notify filter must be at most 512 UTF-8 bytes with no NUL");
    if(!System(c).types.contains(13016)) DeclareEventType(c,13016,{"entity","string"});
    BindEventListener(c,13016,std::move(receiver),true,{std::move(node),std::move(callback),std::move(notify_filter)});
}
void QueueAnimationNotify(Ctx& c,EntityRef entity,std::string notify) {
    if(!c.events || !c.events->types.contains(13016)) return;
    SendEvent(c,13016,{},EntityRef{},{entity,notify});
    if(EntityExists(c,entity)) SendEvent(c,13016,entity,EntityRef{},{entity,std::move(notify)});
}
void BindEvent(Ctx& c, int event, std::string node, EntityRef receiver, bool enabled, EventHandler callback) {
    BindEventListener(c,event,std::move(receiver),enabled,{std::move(node),std::move(callback),{}});
}
void BindEntityLifecycle(Ctx& c,int event,std::string node,EntityRef receiver,EventHandler callback) {
    if(!IsEntityLifecycle(event)) throw std::runtime_error("Invalid entity lifecycle event ID");
    if(!System(c).types.contains(event)) DeclareEventType(c,event,{"entity","bool"});
    BindEvent(c,event,std::move(node),std::move(receiver),true,std::move(callback));
}
void BindInputEvent(Ctx& c,int event,std::string node,std::string filter,EventHandler callback) {
    const auto origin=c.current_node; c.current_node=node;
    if(!IsInputEvent(event) || (!filter.empty() && !InputEventName(c,event,filter)))
        throw std::runtime_error("Invalid input event ID or filter");
    if(!System(c).types.contains(event)) DeclareEventType(c,event,event==10020 ? std::vector<std::string>{"string","bool","int"} : std::vector<std::string>{"string","bool"});
    BindEventListener(c,event,{},true,{std::move(node),std::move(callback),std::move(filter)});
    c.current_node=origin;
}
void QueueInputEvent(Ctx& c,int event,const std::string& name,bool down,std::int64_t controller) {
    if(!c.events || !c.events->types.contains(event)) return;
    const auto& listeners=c.events->subscriptions.at({event,{}}).listeners;
    auto first=std::find_if(listeners.begin(),listeners.end(),[&](const auto& listener){return listener.filter.empty() || listener.filter==name;});
    if(first==listeners.end()) return;
    const auto origin=c.current_node; c.current_node=first->node;
    if(!InputEventName(c,event,name) || (event==10020 ? !IsController(controller) : (event!=10010 && down!=(event==10008 || event==10011))))
        throw std::runtime_error("Invalid input transition");
    std::vector<Value> args{name,down}; if(event==10020) args.push_back(controller);
    SendEvent(c,event,{},{},std::move(args));
    c.current_node=origin;
}
void ClearInputEvents(Ctx& c) {
    if(!c.events) return;
    std::erase_if(c.events->queue,[&](const auto& envelope) {
        if(!IsInputEvent(envelope.target.first)) return false;
        c.events->queued_bytes-=envelope.bytes; return true;
    });
}
void ClearInputActionEvents(Ctx& c,const std::set<std::string>& actions) {
    if(!c.events || actions.empty()) return;
    for(const auto& name:actions) ++c.events->input_epochs[name];
    std::erase_if(c.events->queue,[&](const auto& envelope) {
        if((envelope.target.first!=10011 && envelope.target.first!=10012) || !actions.contains(std::get<std::string>(envelope.args->at(0)))) return false;
        c.events->queued_bytes-=envelope.bytes; return true;
    });
}
static void BindEventListener(Ctx& c,int event,EntityRef receiver,bool enabled,EventListener listener) {
    Owner(c,receiver);
    auto& system=System(c);
    auto type=system.types.find(event);
    if(type==system.types.end()) throw std::runtime_error("Undefined event");
    auto [found,inserted]=system.subscriptions.try_emplace(EventKey{event,receiver.id});
    auto& subscription=found->second;
    if(inserted) {
        subscription.entity=NativeEntity(c,receiver.id);
        subscription.enabled=enabled;
        subscription.active=ReceiverActive(c,{event,receiver.id});
        ecs_observer_desc_t observer{};
        observer.query.terms[0].id=EcsAny;
        observer.query.terms[0].src.id=subscription.entity;
        observer.events[0]=type->second.entity;
        observer.callback=OnCustom;
        observer.ctx=&subscription;
        auto handle=ecs_observer_init(system.world,&observer);
        if(!handle) throw std::runtime_error("Cannot register Flecs custom event observer");
        subscription.observer=handle;
        system.observers.push_back(handle);
    } else if(subscription.enabled!=enabled) throw std::runtime_error("Inconsistent initial event subscription");
    subscription.listeners.push_back(std::move(listener));
    std::sort(subscription.listeners.begin(),subscription.listeners.end(),[](const EventListener& a,const EventListener& b){return a.node<b.node;});
}
namespace {
constexpr std::size_t MaxEventBytes=16*1024*1024, MaxQueueBytes=64*1024*1024, MaxQueuedEvents=4096;
std::size_t JsonEventBytes(const Json& value) {
    std::size_t bytes=sizeof(Json);
    if(value.is_string()) return bytes+value.get_ref<const std::string&>().size();
    if(value.is_structured()) for(auto it=value.begin();it!=value.end();++it) {
        bytes+=JsonEventBytes(it.value());
        if(value.is_object()) bytes+=it.key().size()+sizeof(std::string)+4*sizeof(void*);
        if(bytes>MaxEventBytes) break;
    }
    return bytes;
}
template<class T> std::size_t EventBytes(const T& value) {
    if constexpr(std::is_same_v<T,std::string>) return sizeof(T)+value.size();
    else if constexpr(std::is_same_v<T,EntityRef>) return sizeof(T)+value.id.size();
    else if constexpr(std::is_same_v<T,StructValue>) return sizeof(T)+value.type.size()+JsonEventBytes(value.fields);
    else if constexpr(std::is_same_v<T,EnumValue>) return sizeof(T)+value.type.size()+value.value.size();
    else if constexpr(std::is_same_v<T,UserCollectionValue>) return sizeof(T)+value.type.size()+JsonEventBytes(value.items);
    else if constexpr(ArrayType<T>::value || SetType<T>::value) {
        std::size_t size=sizeof(T);
        for(const auto& item:value) {
            size+=EventBytes<typename T::value_type>(item);
            if(size>MaxEventBytes) break;
        }
        return size;
    } else if constexpr(MapType<T>::value) {
        std::size_t size=sizeof(T);
        for(const auto& [key,item]:value) {
            size+=EventBytes(key)+EventBytes(item)+4*sizeof(void*);
            if(size>MaxEventBytes) break;
        }
        return size;
    } else return sizeof(T);
}
std::size_t PayloadBytes(Ctx& c,EventSystem& system,int event,const std::vector<Value>& args) {
    auto type=system.types.find(event);
    if(type==system.types.end()) throw std::runtime_error("Undefined event");
    if(type->second.types.size()!=args.size()) throw std::runtime_error("Event parameter count mismatch");
    std::size_t bytes=sizeof(args);
    for(std::size_t i=0;i<args.size();++i) {
        bytes+=std::visit([&](const auto& value) {
            using T=std::decay_t<decltype(value)>;
            if(ValueType(args[i])!=type->second.types[i]) throw std::runtime_error("Event payload type mismatch");
            if constexpr(std::is_same_v<T,StructValue> || std::is_same_v<T,EnumValue> || std::is_same_v<T,UserCollectionValue>)
                CheckedValueFromJson(c,ValueType(args[i]),ToJson(value));
            CheckValue(value);
            return EventBytes(value)+sizeof(Value);
        },args[i]);
        if(bytes>MaxEventBytes) throw std::runtime_error("Event payload exceeds 16 MiB storage limit");
    }
    return bytes;
}
void Enqueue(Ctx& c,int event,EntityRef sender,std::vector<Value> args,const std::vector<EventKey>& targets) {
    auto& system=System(c);
    Owner(c,sender);
    const auto payload_bytes=PayloadBytes(c,system,event,args);
    std::size_t bytes=0;
    for(const auto& key:targets) bytes+=payload_bytes+sizeof(Envelope)+key.second.size()+sender.id.size()+c.current_node.size();
    if(targets.size()>MaxQueuedEvents-system.queue.size() || bytes>MaxQueueBytes-system.queued_bytes)
        throw std::runtime_error("Event queue exceeds 4096 deliveries or 64 MiB storage limit");
    auto shared=std::make_shared<const std::vector<Value>>(std::move(args));
    for(const auto& key:targets) {
        const auto size=payload_bytes+sizeof(Envelope)+key.second.size()+sender.id.size()+c.current_node.size();
        system.queue.push_back({key,sender,shared,system.subscriptions.at(key).epoch,c.current_node,size});
        system.queued_bytes+=size;
    }
}
}
void SendEvent(Ctx& c,int event,EntityRef recipient,EntityRef sender,std::vector<Value> args) {
    if(event==1009) throw std::runtime_error("Object Destroyed must run synchronously before deletion");
    Owner(c,recipient);
    auto& system=System(c);
    EventKey key{event,recipient.id};
    auto found=system.subscriptions.find(key);
    std::vector<EventKey> targets;
    if(found!=system.subscriptions.end() && found->second.enabled && found->second.active) targets.push_back(key);
    Enqueue(c,event,std::move(sender),std::move(args),targets);
}
void BroadcastEvent(Ctx& c,int event,EntityRef sender,std::vector<Value> args) {
    if(event==1009) throw std::runtime_error("Object Destroyed must run synchronously before deletion");
    std::vector<EventKey> targets;
    for(const auto& [key,subscription]:System(c).subscriptions)
        if(key.first==event && subscription.enabled && subscription.active) targets.push_back(key);
    Enqueue(c,event,std::move(sender),std::move(args),targets);
}
static bool HasEntityLifecycle(const EventSystem& system) {
    return std::any_of(system.types.begin(),system.types.end(),[](const auto& type){return IsEntityLifecycle(type.first);});
}
static std::map<std::string,bool> EntityActivity(Ctx& c) {
    std::map<std::string,bool> result;
    for(const auto& entity:GetAllEntities(c)) result.emplace(entity.id,IsEntityActive(c,entity));
    return result;
}
static void RefreshEntityLifecycle(Ctx& c) {
    auto& system=*c.events;
    if(!system.lifecycle_started) return;
    auto next=EntityActivity(c);
    for(const auto& [id,active]:next) {
        auto before=system.lifecycle_entities.find(id);
        auto emit=[&](int event) {
            if(!system.types.contains(event)) return;
            std::vector<EventKey> targets;
            for(const auto& receiver:{std::string{},id}) {
                EventKey key{event,receiver}; auto found=system.subscriptions.find(key);
                if(found!=system.subscriptions.end() && found->second.enabled && found->second.active) targets.push_back(key);
            }
            Enqueue(c,event,{}, {EntityRef{id},active},targets);
        };
        if(before==system.lifecycle_entities.end()) { emit(1006); if(active) emit(1007); }
        else if(before->second!=active) emit(active ? 1007 : 1008);
    }
    system.lifecycle_entities=std::move(next);
}
void StartEntityLifecycle(Ctx& c) {
    auto& system=System(c);
    if(system.lifecycle_started || !HasEntityLifecycle(system)) return;
    system.lifecycle_started=true;
    RefreshEntityLifecycle(c);
}
bool HasEntityDestroyedListeners(const Ctx& c) {
    return c.events && c.events->lifecycle_started && c.events->types.contains(1009);
}
bool DispatchingEntityDestroyed(const Ctx& c) { return c.events && c.events->notifying_destruction; }
void NotifyEntityDestroyed(Ctx& c,EntityRef entity) {
    if(!HasEntityDestroyedListeners(c)) return;
    auto& system=*c.events;
    if(system.notifying_destruction) throw std::runtime_error("Nested destruction notification must be deferred");
    struct Guard { bool& flag; ~Guard(){flag=false;} } guard{system.notifying_destruction};
    system.notifying_destruction=true;
    const auto origin=c.current_node;
    auto args=std::make_shared<const std::vector<Value>>(std::vector<Value>{entity,IsEntityActive(c,entity)});
    for(const auto& receiver:{std::string{},entity.id}) {
        const EventKey key{1009,receiver}; auto found=system.subscriptions.find(key);
        if(found==system.subscriptions.end() || !found->second.enabled || !found->second.active) continue;
        Tick(c,origin);
        const auto& subscription=found->second;
        Envelope envelope{key,{},args,subscription.epoch,origin,0};
        CustomDelivery delivery{c,envelope,{}, {}};
        ecs_event_desc_t event{}; event.event=system.types.at(1009).entity;
        event.entity=subscription.entity; event.param=&delivery; ecs_emit(system.world,&event);
        if(delivery.error) std::rethrow_exception(delivery.error);
        for(const auto& listener:delivery.listeners) {
            EventScope scope(c); c.self=receiver;
            Tick(c,listener.node); listener.callback(c,{},EntityRef{receiver},*args);
        }
    }
    c.current_node=origin; // Keep the originating operation on later commit failures.
}
void SetEventSubscription(Ctx& c,int event,EntityRef recipient,bool enabled) {
    if(IsBuiltinEvent(event)) throw std::runtime_error("Builtin event subscriptions follow their receiver lifetime");
    Owner(c,recipient);
    auto& system=System(c);
    auto found=system.subscriptions.find({event,recipient.id});
    if(found==system.subscriptions.end()) throw std::runtime_error("No handler for this event and receiver");
    if(found->second.enabled!=enabled) {
        found->second.enabled=enabled;
        ++found->second.epoch; // Invalidates queued events across unsubscribe/resubscribe.
    }
}
void DrainEvents(Ctx& c) {
    auto& system=System(c);
    if(system.draining || system.notifying_destruction) return;
    struct Guard { bool& draining; ~Guard(){draining=false;} } guard{system.draining};
    system.draining=true;
    try {
        while(!system.queue.empty()) {
            auto envelope=std::move(system.queue.front()); system.queue.pop_front();
            system.queued_bytes-=envelope.bytes;
            Tick(c,envelope.origin);
            const auto& subscription=system.subscriptions.at(envelope.target);
            if(!subscription.enabled || !subscription.active || subscription.epoch!=envelope.epoch) continue;
            const auto activity_epoch=subscription.activity_epoch;
            const bool mapped=envelope.target.first==10011 || envelope.target.first==10012;
            const auto action=mapped ? std::get<std::string>(envelope.args->at(0)) : std::string();
            const auto input_epoch=mapped ? system.input_epochs[action] : 0;
            CustomDelivery delivery{c,envelope,{}, {}};
            ecs_event_desc_t event{};
            event.event=system.types.at(envelope.target.first).entity;
            event.entity=subscription.entity;
            event.param=&delivery;
            ecs_emit(system.world,&event);
            if(delivery.error) std::rethrow_exception(delivery.error);
            for(const auto& listener:delivery.listeners) {
                if(!ReceiverActive(c,envelope.target) || subscription.activity_epoch!=activity_epoch) break;
                if(mapped && system.input_epochs[action]!=input_epoch) break;
                if((IsAnimationFinishedEvent(envelope.target.first) || IsAnimationNotifyEvent(envelope.target.first) || IsInputEvent(envelope.target.first)) && !listener.filter.empty() &&
                   listener.filter!=std::get<std::string>(envelope.args->at(IsInputEvent(envelope.target.first) ? 0 : 1))) continue;
                EventScope scope(c); c.self=envelope.target.second;
                Tick(c,listener.node);
                listener.callback(c,envelope.sender,EntityRef{c.self},*envelope.args);
            }
        }
    } catch(...) {
        system.queue.clear(); system.queued_bytes=0;
        throw;
    }
}
Json EventSnapshot(const Ctx& c) {
    Json subscriptions=Json::array();
    if(c.events) for(const auto& [key,value]:c.events->subscriptions)
        if(key.second.empty() || EntityExists(c,{key.second}))
            subscriptions.push_back({{"event",key.first},{"receiver",key.second},{"enabled",value.enabled}});
    Json result={{"subscriptions",subscriptions},{"pending",c.events ? c.events->queue.size() : 0}};
    if(c.events && HasEntityLifecycle(*c.events)) result["lifecycle_started"]=c.events->lifecycle_started;
    return result;
}
namespace {
void CheckpointCheck(bool valid,const char* message) {
    if(!valid) throw std::runtime_error(message);
}
void CheckpointBoundary(const EventSystem& s) {
    CheckpointCheck(!s.draining && !s.advancing && !s.notifying_destruction,"Event checkpoint requires a callback boundary");
}
std::string ClockText(long double value) {
    std::ostringstream text;
    text.imbue(std::locale::classic());
    text << std::setprecision(std::numeric_limits<long double>::max_digits10) << value;
    return text.str();
}
long double ReadClock(const Json& value) {
    const auto text=value.get<std::string>();
    CheckpointCheck(!text.empty() && text.size()<=128,"Invalid checkpoint timer clock");
    std::istringstream input(text); input.imbue(std::locale::classic());
    long double number=0;
    input >> std::noskipws >> number;
    CheckpointCheck(!input.fail() && input.eof() && number>=0 && std::isfinite(static_cast<double>(number)),
                    "Invalid checkpoint timer clock");
    return number;
}
std::uint64_t ReadCounter(const Json& value) {
    CheckpointCheck(value.is_number_integer() && value>=0,"Invalid checkpoint counter");
    return value.get<std::uint64_t>();
}
std::string Origin(const Json& value) {
    auto text=value.get<std::string>();
    CheckpointCheck(text.size()<=512 && text.find('\0')==std::string::npos,"Invalid checkpoint node identity");
    return text;
}
Json BindingIdentity(const EventSystem& s) {
    Json timers=Json::array(),events=Json::array(),types=Json::array();
    for(const auto& [id,type]:s.types) types.push_back({{"id",id},{"types",type.types}});
    for(const auto& [owner,receiver]:s.receivers) {
        auto listeners=Json::array();
        for(const auto& listener:receiver.listeners) listeners.push_back({{"node",listener.node},{"filter",listener.filter}});
        timers.push_back({{"owner",owner},{"listeners",listeners}});
    }
    for(const auto& [key,subscription]:s.subscriptions) {
        auto listeners=Json::array();
        for(const auto& listener:subscription.listeners) {
            if(IsAnimationFinishedEvent(key.first) || IsAnimationNotifyEvent(key.first) || IsInputEvent(key.first)) listeners.push_back({{"node",listener.node},{"filter",listener.filter}});
            else listeners.push_back(listener.node);
        }
        events.push_back({{"event",key.first},{"receiver",key.second},{"listeners",listeners}});
    }
    return {{"types",types},{"timers",timers},{"events",events}};
}
EventKey ReadEventKey(const Json& entry) {
    const auto id=FromJson<std::int64_t>(entry.at("event"));
    CheckpointCheck(IsBuiltinEvent(id) || (id>=100000 && id<=199999),"Invalid checkpoint event ID");
    return {static_cast<int>(id),entry.at("receiver").get<std::string>()};
}
}
Json EventCheckpoint(const Ctx& c) {
    CheckpointCheck(bool(c.events),"Event system is not initialized");
    const auto& s=*c.events; CheckpointBoundary(s);
    Json timers=Json::array(),receivers=Json::array(),subscriptions=Json::array(),queue=Json::array();
    for(const auto& [key,t]:s.timers) timers.push_back({{"owner",key.first},{"name",key.second},
        {"deadline",ClockText(t.deadline)},{"interval",ClockText(t.interval)},{"remaining",ClockText(t.remaining)},
        {"repeat",t.repeat},{"paused",t.paused},{"suspended",t.suspended},{"unscaled",t.unscaled},{"serial",t.serial},{"origin",t.origin}});
    for(const auto& [owner,r]:s.receivers) receivers.push_back({{"owner",owner},{"active",r.active},{"epoch",r.epoch}});
    for(const auto& [key,s]:s.subscriptions) subscriptions.push_back({{"event",key.first},{"receiver",key.second},
        {"enabled",s.enabled},{"active",s.active},{"epoch",s.epoch},{"activity_epoch",s.activity_epoch}});
    for(const auto& e:s.queue) {
        auto args=Json::array();
        for(const auto& arg:*e.args) args.push_back(std::visit([](const auto& v){return ToJson(v);},arg));
        queue.push_back({{"event",e.target.first},{"receiver",e.target.second},{"sender",e.sender.id},
            {"args",args},{"epoch",e.epoch},{"origin",e.origin}});
    }
    Json result={{"version",2},{"bindings",BindingIdentity(s)},{"clock",ClockText(s.clock)},{"unscaled_clock",ClockText(s.unscaled_clock)},{"serial",s.serial},
        {"timers",timers},{"receivers",receivers},{"subscriptions",subscriptions},{"queue",queue}};
    if(HasEntityLifecycle(s)) { result["version"]=3; result["lifecycle_started"]=s.lifecycle_started; }
    return result;
}
void RestoreEventCheckpoint(Ctx& target,const Ctx& bindings,const Json& data) {
    CheckpointCheck(bool(bindings.events),"Event bindings are not initialized");
    const auto original=bindings.events; CheckpointBoundary(*original);
    if(target.events) CheckpointBoundary(*target.events);
    CheckpointCheck(data.is_object() && data.at("version").is_number_integer() &&
        ((data.at("version")==1 && data.size()==8) || (data.at("version")==2 && data.size()==9) || (data.at("version")==3 && data.size()==10)),
                    "Invalid event checkpoint version or fields");
    CheckpointCheck((data.at("version")==3)==HasEntityLifecycle(*original),"Checkpoint entity lifecycle state does not match this program");
    const bool legacy=data.at("version")==1;
    CheckpointCheck(data.at("bindings")==BindingIdentity(*original),"Checkpoint event bindings do not match this program");
    CheckpointCheck(data.at("timers").is_array() && data.at("timers").size()<=4096 &&
        data.at("receivers").is_array() && data.at("receivers").size()==original->receivers.size() &&
        data.at("subscriptions").is_array() && data.at("subscriptions").size()==original->subscriptions.size() &&
        data.at("queue").is_array() && data.at("queue").size()<=MaxQueuedEvents,"Invalid event checkpoint collection");
    // The staging system holds the candidate world alive. No target callback,
    // timer, subscription or queue is changed until every record is accepted.
    Ctx staging; staging.world=target.world; staging.user_types=target.user_types; staging.events=CreateEventSystem(staging);
    auto& s=*staging.events;
    if(data.at("version")==3) {
        s.lifecycle_started=data.at("lifecycle_started").get<bool>();
        if(s.lifecycle_started) s.lifecycle_entities=EntityActivity(staging);
    }
    s.clock=ReadClock(data.at("clock")); s.serial=ReadCounter(data.at("serial"));
    s.unscaled_clock=legacy ? s.clock : ReadClock(data.at("unscaled_clock"));
    for(const auto& [id,type]:original->types) DeclareEventType(staging,id,type.types);
    for(const auto& [owner,receiver]:original->receivers) {
        if(owner.empty() || EntityExists(staging,{owner})) {
            for(const auto& listener:receiver.listeners) BindTimer(staging,listener.node,{owner},listener.filter,listener.callback);
        } else {
            auto& missing=s.receivers[owner]; missing.active=false; missing.listeners=receiver.listeners;
        }
    }
    for(const auto& [key,subscription]:original->subscriptions) {
        if(key.second.empty() || EntityExists(staging,{key.second})) {
            for(const auto& listener:subscription.listeners) BindEventListener(staging,key.first,{key.second},false,listener);
        } else {
            auto& missing=s.subscriptions[key]; missing.entity=0; missing.enabled=false; missing.active=false;
            missing.listeners=subscription.listeners;
        }
    }
    std::set<std::string> receivers;
    for(const auto& entry:data.at("receivers")) {
        CheckpointCheck(entry.is_object() && entry.size()==3,"Invalid checkpoint timer receiver");
        const auto owner=entry.at("owner").get<std::string>();
        CheckpointCheck(s.receivers.contains(owner) && receivers.insert(owner).second,"Unknown or duplicate checkpoint timer receiver");
        auto& receiver=s.receivers.at(owner);
        receiver.active=entry.at("active").get<bool>(); receiver.epoch=ReadCounter(entry.at("epoch"));
        CheckpointCheck(receiver.active==OwnerActive(staging,owner),"Checkpoint timer receiver activity disagrees with scene");
    }
    std::set<EventKey> subscriptions;
    for(const auto& entry:data.at("subscriptions")) {
        CheckpointCheck(entry.is_object() && entry.size()==6,"Invalid checkpoint event subscription");
        const auto key=ReadEventKey(entry);
        CheckpointCheck(s.subscriptions.contains(key) && subscriptions.insert(key).second,"Unknown or duplicate checkpoint event subscription");
        auto& subscription=s.subscriptions.at(key);
        subscription.enabled=entry.at("enabled").get<bool>(); subscription.active=entry.at("active").get<bool>();
        subscription.epoch=ReadCounter(entry.at("epoch")); subscription.activity_epoch=ReadCounter(entry.at("activity_epoch"));
        if(IsGameSaveEvent(key.first) || IsInputEvent(key.first) || IsWorldPauseEvent(key.first) || IsSceneFailure(key.first)) CheckpointCheck(key.second.empty() && subscription.enabled && subscription.active &&
            subscription.epoch==0 && subscription.activity_epoch==0,"Invalid checkpoint persistence subscription");
        if(IsPhysicsEvent(key.first) || IsAnimationFinishedEvent(key.first) || IsAnimationNotifyEvent(key.first) || IsEntityLifecycle(key.first)) CheckpointCheck(
            subscription.enabled==(key.second.empty()||EntityExists(staging,{key.second})) &&
            (!key.second.empty() || (subscription.epoch==0 && subscription.activity_epoch==0)),
            "Invalid checkpoint entity event subscription");
        CheckpointCheck(subscription.activity_epoch<=subscription.epoch && subscription.active==ReceiverActive(staging,key) &&
            (!subscription.enabled || key.second.empty() || EntityExists(staging,{key.second})),"Invalid checkpoint subscription activity");
    }
    std::set<std::uint64_t> serials;
    for(const auto& entry:data.at("timers")) {
        CheckpointCheck(entry.is_object() && entry.size()==(legacy ? 10 : 11),"Invalid checkpoint timer");
        const auto key=TimerKey(staging,entry.at("name").get<std::string>(),{entry.at("owner").get<std::string>()});
        Timer timer{ReadClock(entry.at("deadline")),ReadClock(entry.at("interval")),ReadClock(entry.at("remaining")),
            entry.at("repeat").get<bool>(),entry.at("paused").get<bool>(),ReadCounter(entry.at("serial")),Origin(entry.at("origin")),entry.at("suspended").get<bool>(),
            legacy ? false : entry.at("unscaled").get<bool>()};
        CheckpointCheck(timer.serial>0 && timer.serial<=s.serial && serials.insert(timer.serial).second &&
            (!timer.repeat || timer.interval>0) && timer.suspended==!OwnerActive(staging,key.first),"Invalid checkpoint timer state");
        CheckpointCheck(s.timers.emplace(key,std::move(timer)).second,"Duplicate checkpoint timer");
    }
    for(const auto& entry:data.at("queue")) {
        CheckpointCheck(entry.is_object() && entry.size()==6 && entry.at("args").is_array(),"Invalid checkpoint queued event");
        const auto key=ReadEventKey(entry);
        CheckpointCheck(s.subscriptions.contains(key),"Unknown checkpoint event recipient");
        const auto& types=s.types.at(key.first).types;
        CheckpointCheck(types.size()==entry.at("args").size(),"Checkpoint event parameter count mismatch");
        std::vector<Value> args;
        for(std::size_t i=0;i<types.size();++i) args.push_back(CheckedValueFromJson(target,types[i],entry.at("args").at(i)));
        EntityRef sender{entry.at("sender").get<std::string>()}; CheckValue(sender);
        if(IsInputEvent(key.first)) {
            const auto& name=std::get<std::string>(args.at(0)); const bool down=std::get<bool>(args.at(1));
            CheckpointCheck(key.second.empty() && sender.id.empty() && InputEventName(target,key.first,name) &&
                (key.first==10020 ? IsController(std::get<std::int64_t>(args.at(2))) :
                 key.first==10010 || down==(key.first==10008 || key.first==10011)),"Invalid checkpoint input event payload");
            CheckpointCheck(key.first!=10011 || InputActionAvailable(target,name),"Unavailable action has a queued press");
        }
        if(IsEntityLifecycle(key.first)) {
            const auto& entity=std::get<EntityRef>(args.at(0)); const bool active=std::get<bool>(args.at(1));
            CheckpointCheck(key.first!=1009 && s.lifecycle_started && sender.id.empty() && !entity.id.empty() &&
                (key.second.empty() || key.second==entity.id) && (key.first==1006 || active==(key.first==1007)),
                "Invalid checkpoint entity lifecycle payload");
        }
        const auto origin=Origin(entry.at("origin")); const auto epoch=ReadCounter(entry.at("epoch"));
        const auto bytes=PayloadBytes(target,s,key.first,args)+sizeof(Envelope)+key.second.size()+sender.id.size()+origin.size();
        CheckpointCheck(epoch<=s.subscriptions.at(key).epoch && bytes<=MaxQueueBytes-s.queued_bytes,"Invalid checkpoint event epoch or queue size");
        s.queue.push_back({key,std::move(sender),std::make_shared<const std::vector<Value>>(std::move(args)),epoch,origin,bytes});
        s.queued_bytes+=bytes;
    }
    target.events=std::move(staging.events);
}
void ForgetEntityEvents(Ctx& c,const std::string& id) {
    if(!c.events) return;
    auto& s=*c.events;
    std::erase_if(s.timers,[&](const auto& item){return item.first.first==id;});
    if(auto receiver=s.receivers.find(id); receiver!=s.receivers.end()) {
        receiver->second.active=false; ++receiver->second.epoch;
    }
    for(auto& [key,value]:s.subscriptions) if(key.second==id) {
        value.enabled=false; value.active=false; ++value.epoch; ++value.activity_epoch;
    }
    std::erase_if(s.queue,[&](const auto& envelope) {
        if(envelope.target.second!=id) return false;
        s.queued_bytes-=envelope.bytes;
        return true;
    });
    // Keep observer contexts stable until teardown. Flecs determines recipients;
    // graph callbacks use a listener snapshot outside the observer defer scope.
}
void RestoreEntityEvents(Ctx& c,const std::string& id) {
    if(!c.events) return;
    auto& s=*c.events;
    const auto entity=NativeEntity(c,id);
    auto replace=[&](ecs_entity_t& previous,ecs_entity_t event,ecs_iter_action_t callback,void* context) {
        if(previous && ecs_is_alive(s.world,previous)) ecs_delete(s.world,previous);
        std::erase(s.observers,previous);
        ecs_observer_desc_t observer{};
        observer.query.terms[0].id=EcsAny;
        observer.query.terms[0].src.id=entity;
        observer.events[0]=event; observer.callback=callback; observer.ctx=context;
        previous=ecs_observer_init(s.world,&observer);
        if(!previous) throw std::runtime_error("Cannot restore Flecs entity observer");
        s.observers.push_back(previous);
    };
    if(auto found=s.receivers.find(id); found!=s.receivers.end()) {
        auto& receiver=found->second; receiver.entity=entity;
        replace(receiver.observer,s.timer_event,OnTimer,&receiver);
    }
    for(auto& [key,subscription]:s.subscriptions) if(key.second==id) {
        subscription.entity=entity;
        if(IsPhysicsEvent(key.first) || IsAnimationFinishedEvent(key.first) || IsAnimationNotifyEvent(key.first) || IsEntityLifecycle(key.first)) subscription.enabled=true;
        replace(subscription.observer,s.types.at(key.first).entity,OnCustom,&subscription);
    }
}
}
