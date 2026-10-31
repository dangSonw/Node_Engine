#include "runtime.hpp"
namespace rt {
void ValidateFrameEvents(const Json& program) {
    const auto& events=program.at("events");
    if(!events.is_object()) throw std::runtime_error("IR events must be an object");
    for(const auto* phase:{"start","update","fixed_update","late_update","quit","scene_loaded"}) {
        const bool required=std::string_view(phase)=="start" || std::string_view(phase)=="update";
        if((required || events.contains(phase)) && (!events.contains(phase) || !events.at(phase).is_array()))
            throw std::runtime_error(std::string("IR ")+phase+" statements must be an array");
    }
    if(events.contains("scene_failure")) {
        const auto& handlers=events.at("scene_failure");
        if(!handlers.is_array()) throw std::runtime_error("IR scene_failure handlers must be an array");
        for(const auto& h:handlers) {
            if(!h.is_object() || h.size()!=3 || !h.contains("node") || !h.at("node").is_string() ||
               h.at("node").get_ref<const std::string&>().empty() || !h.contains("event") ||
               !h.at("event").is_number_integer() || h.at("event")!=1020 || !h.contains("body") || !h.at("body").is_array())
                throw std::runtime_error("Invalid IR scene_failure handler");
        }
    }
    if(events.contains("world_pause")) {
        const auto& handlers=events.at("world_pause");
        if(!handlers.is_array()) throw std::runtime_error("IR world_pause handlers must be an array");
        for(const auto& h:handlers) {
            if(!h.is_object() || h.size()!=3 || !h.contains("node") || !h.at("node").is_string() ||
               h.at("node").get_ref<const std::string&>().empty() || !h.contains("event") ||
               !h.at("event").is_number_integer() || (h.at("event")!=1017 && h.at("event")!=1018) ||
               !h.contains("body") || !h.at("body").is_array())
                throw std::runtime_error("Invalid IR world_pause handler");
        }
    }
}
void SetTimeScale(Ctx& c,double scale) {
    if(!std::isfinite(scale) || scale<0) throw std::runtime_error("Time Scale must be finite and nonnegative");
    c.time_scale=scale;
}
double GetTimeScale(Ctx& c) { return c.time_scale; }
static void SetWorldPaused(Ctx& c,bool paused) {
    if(c.world_paused==paused) return;
    QueueWorldPauseEvent(c,paused);
    c.world_paused=paused;
}
void PauseWorld(Ctx& c) { SetWorldPaused(c,true); }
void ResumeWorld(Ctx& c) { SetWorldPaused(c,false); }
bool IsWorldPaused(Ctx& c) { return c.world_paused; }
double UnscaledDeltaTime(Ctx& c) { return c.unscaled_dt; }
double RealTime(Ctx& c) { return c.real_time; }
double FixedDeltaTime() { return FixedStep; }
void BeginGameFrame(Ctx& c,double elapsed,double step) {
    if(!std::isfinite(elapsed) || elapsed<0 || !std::isfinite(step) || step<0 || step>60 || step>elapsed)
        throw std::runtime_error("Invalid elapsed time or unscaled frame step (0..60 seconds, at most elapsed time)");
    const auto scaled=c.world_paused ? 0.0 : finite(step*c.time_scale);
    if(scaled>1) throw std::runtime_error("Scaled frame exceeds 1 second; lower Time Scale or frame delta");
    if(c.frame==UINT64_MAX) throw std::runtime_error("Game frame counter exhausted");
    // Fail before gameplay if either clock would overflow after this frame.
    (void)finite(c.time+scaled); (void)finite(c.real_time+elapsed);
    c.real_dt=elapsed; c.unscaled_dt=step; c.dt=scaled; c.time_frozen=c.world_paused || c.time_scale==0;
}
void EndGameFrame(Ctx& c) {
    c.time=finite(c.time+c.dt); c.real_time=finite(c.real_time+c.real_dt); ++c.frame;
    if(c.autosave_interval>0) {
        c.autosave_elapsed=finite(c.autosave_elapsed+c.real_dt);
        if(c.autosave_elapsed>=c.autosave_interval) {
            c.autosave_elapsed=std::fmod(c.autosave_elapsed,c.autosave_interval);
            if(c.game_persistence && !GameSavePending(c) && !c.quit_dispatched) {
                if(c.saves.game.empty()) (void)OpenSaveStorage(c,"autosave");
                if(!c.saves.game.empty() && c.saves.ok && !GameSavePending(c)) (void)SaveGame(c,"autosave");
            }
        }
    }
}
}
