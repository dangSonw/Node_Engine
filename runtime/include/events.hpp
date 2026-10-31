#pragma once
#include "values.hpp"
#include <functional>
#include <memory>
#include <set>

namespace rt {
struct Ctx;
struct EventSystem;
struct PhysicsContact;
using TimerHandler = std::function<void(Ctx&, const std::string&, EntityRef)>;
using EventHandler = std::function<void(Ctx&, EntityRef, EntityRef, const std::vector<Value>&)>;
std::shared_ptr<EventSystem> CreateEventSystem(Ctx&);
void ForgetEntityEvents(Ctx&, const std::string&);
void RestoreEntityEvents(Ctx&, const std::string&);
void RefreshEntityActivity(Ctx&);
void BindTimer(Ctx&, std::string node, EntityRef owner, std::string filter, TimerHandler);
void BindInterpretedEvents(Ctx&, const Json& ir);
// Builtin global listeners use the same bounded queue and checkpoint bindings.
void BindGameSaveEvent(Ctx&, int event, std::string node, EventHandler);
void QueueGameSaveEvent(Ctx&, bool load, bool success, std::string slot, std::string error);
void BindWorldPauseEvent(Ctx&,int event,std::string node,EventHandler);
void QueueWorldPauseEvent(Ctx&,bool paused);
void BindSceneLoadFailed(Ctx&,std::string node,EventHandler);
void QueueSceneLoadFailed(Ctx&,std::string scene,std::string error);
void BindPhysicsEvent(Ctx&, int event, std::string node, EntityRef receiver, EventHandler);
void QueuePhysicsContact(Ctx&, const PhysicsContact&);
void BindAnimationFinished(Ctx&, std::string node, EntityRef receiver, std::string clip_filter, EventHandler);
void QueueAnimationFinished(Ctx&, EntityRef, std::string clip);
void BindAnimationNotify(Ctx&, std::string node, EntityRef receiver, std::string notify_filter, EventHandler);
void QueueAnimationNotify(Ctx&, EntityRef, std::string notify);
void BindInputEvent(Ctx&, int event, std::string node, std::string filter, EventHandler);
void QueueInputEvent(Ctx&, int event, const std::string& name, bool down, std::int64_t controller=0);
void ClearInputEvents(Ctx&);
void ClearInputActionEvents(Ctx&,const std::set<std::string>& actions);
void BindEntityLifecycle(Ctx&, int event, std::string node, EntityRef receiver, EventHandler);
// Called only when starting a fresh game, after resources and handlers are ready.
void StartEntityLifecycle(Ctx&);
bool HasEntityDestroyedListeners(const Ctx&);
bool DispatchingEntityDestroyed(const Ctx&);
void NotifyEntityDestroyed(Ctx&,EntityRef);
void StartTimer(Ctx&, std::string name, double seconds, bool repeat, EntityRef owner, bool unscaled=false);
void StopTimer(Ctx&, std::string name, EntityRef owner);
void PauseTimer(Ctx&, std::string name, EntityRef owner);
void ResumeTimer(Ctx&, std::string name, EntityRef owner);
bool TimerExists(Ctx&, std::string name, EntityRef owner);
bool IsTimerPaused(Ctx&, std::string name, EntityRef owner);
double TimerRemaining(Ctx&, std::string name, EntityRef owner);
void AdvanceTimers(Ctx&);
Json TimerSnapshot(const Ctx&);
void DeclareEvent(Ctx&, int event, std::vector<std::string> types);
void BindEvent(Ctx&, int event, std::string node, EntityRef receiver, bool enabled, EventHandler);
void SendEvent(Ctx&, int event, EntityRef recipient, EntityRef sender, std::vector<Value> args);
void BroadcastEvent(Ctx&, int event, EntityRef sender, std::vector<Value> args);
void SetEventSubscription(Ctx&, int event, EntityRef recipient, bool enabled);
void DrainEvents(Ctx&);
Json EventSnapshot(const Ctx&);
// Checkpoints contain state and binding identities, never executable callbacks.
// Restore resolves callbacks from this program and commits only after validation.
// Both calls require an event/timer callback boundary.
Json EventCheckpoint(const Ctx&);
void RestoreEventCheckpoint(Ctx& target, const Ctx& bindings, const Json&);
}
