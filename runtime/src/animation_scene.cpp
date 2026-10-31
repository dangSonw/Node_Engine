#include "runtime.hpp"

namespace rt {
namespace {
void check(bool okay,const char* message) { if(!okay) throw std::runtime_error(message); }
void speed(double value) { check(std::isfinite(value) && std::abs(value)<=100,"Animation speed must be finite and between -100 and 100"); }
const AnimationAsset& asset(Ctx& c,const std::string& mesh) {
    check(!mesh.empty(),"Entity has no model for animation");
    auto& scene=c.animation;
    if(auto it=scene.assets.find(mesh);it!=scene.assets.end()) return *it->second;
    check(!scene.root.empty(),"Host has not prepared animation assets");
    const auto path=std::filesystem::canonical(scene.root/std::filesystem::u8path(mesh));
    const auto relative=path.lexically_relative(scene.root);
    check(!relative.empty() && !relative.is_absolute() && *relative.begin()!="..","Animation model escapes the project root");
    auto loaded=AnimationAsset::Load(path);
    return *scene.assets.emplace(mesh,std::move(loaded)).first->second;
}
size_t clip_index(const AnimationAsset& a,const std::string& name) {
    for(size_t i=0;i<a.clips().size();++i) if(a.clips()[i].name==name) return i;
    throw std::runtime_error("Unknown animation clip: "+name);
}
const AnimationPlayer* player(const Ctx& c,EntityRef e) {
    const auto mesh=GetEntityMesh(c,e);
    const auto it=c.animation.players.find(e.id);
    return it!=c.animation.players.end() && it->second.mesh==mesh ? &it->second : nullptr;
}
AnimationPlayer& required(Ctx& c,EntityRef e) {
    check(player(c,e)!=nullptr,"Entity has no selected animation; use Play Animation first");
    return c.animation.players.at(e.id);
}
double duration(const Ctx& c,const AnimationPlayer& p) { return c.animation.assets.at(p.mesh)->clips().at(p.index).duration; }
void validate_pose(const Ctx& c,const AnimationPlayer& p) { (void)c.animation.assets.at(p.mesh)->sample(p.index,p.time); }
AnimationPlayer select_player(Ctx& c,EntityRef e,std::string clip,bool loop,double rate) {
    speed(rate); const auto mesh=GetEntityMesh(c,e); const auto& a=asset(c,mesh);
    const auto index=clip_index(a,clip); const double length=a.clips()[index].duration;
    AnimationPlayer p; p.mesh=mesh; p.clip=std::move(clip); p.index=index; p.time=rate<0 ? length : 0;
    p.speed=rate; p.loop=loop; p.playing=length>0; p.paused=false;
    validate_pose(c,p); return p;
}
void blend_duration(double value) { check(std::isfinite(value) && value>=0 && value<=60,"Animation blend duration must be between 0 and 60 seconds"); }
void advance_clock(const AnimationAsset& a,size_t index,double& time,double speed_value,bool loop,double dt) {
    const double length=a.clips().at(index).duration;
    const double next=finite(time+finite(dt*speed_value));
    if(loop && length>0) { time=std::fmod(next,length); if(time<0) time+=length; }
    else time=std::clamp(next,0.,length);
}
void emit_notifies(Ctx& c,EntityRef entity,const AnimationPlayer& player,double previous,double next,double length) {
    if(length<=0 || !c.world) return;
    const auto features=FeatureMetadata(c);
    if(!features.contains("3d") || !features.at("3d").is_object()) return;
    const auto& three_d=features.at("3d");
    if(!three_d.contains("animation") || !three_d.at("animation").is_object()) return;
    const auto& animation=three_d.at("animation");
    const auto notifies=animation.value("notifies",Json::array());
    if(!notifies.is_array()) return;
    const bool wrapped=player.loop && ((player.speed>=0 && next<previous) || (player.speed<0 && next>previous));
    for(const auto& notify:notifies) {
        if(!notify.is_object() || notify.value("clip",player.clip)!=player.clip || !notify.contains("name") || !notify.at("name").is_string() ||
           !notify.contains("time") || !notify.at("time").is_number()) continue;
        const auto time=notify.at("time").get<double>();
        if(!std::isfinite(time) || time<0 || time>length) continue;
        const bool crossed=player.speed>=0 ? (wrapped ? time>previous || time<=next : time>previous && time<=next) :
            (wrapped ? time<previous || time>=next : time<previous && time>=next);
        if(crossed) QueueAnimationNotify(c,entity,notify.at("name").get<std::string>());
    }
}
}
void PrepareAnimations(Ctx& c,const std::filesystem::path& root) { c.animation.root=std::filesystem::canonical(root); }
Array<std::string> GetAnimationClips(Ctx& c,EntityRef e) {
    Array<std::string> result;
    for(const auto& clip:asset(c,GetEntityMesh(c,e)).clips()) result.push_back(clip.name);
    return result;
}
void PlayAnimation(Ctx& c,EntityRef e,std::string clip,bool loop,double rate) {
    auto p=select_player(c,e,std::move(clip),loop,rate);
    const bool finished=!p.playing && !p.loop;
    c.animation.players.insert_or_assign(e.id,std::move(p));
    if(finished) QueueAnimationFinished(c,e,c.animation.players.at(e.id).clip);
}
void PlayAnimationBlended(Ctx& c,EntityRef e,std::string clip,bool loop,double rate,double blend) {
    blend_duration(blend);
    if(blend<=0 || !player(c,e)) { PlayAnimation(c,e,std::move(clip),loop,rate); return; }
    const auto previous=*player(c,e);
    auto next=select_player(c,e,std::move(clip),loop,rate);
    next.blend_clip=previous.clip; next.blend_index=previous.index; next.blend_time=previous.time;
    next.blend_speed=previous.speed; next.blend_loop=previous.loop;
    next.blend_duration=blend; next.blend_elapsed=0;
    c.animation.players.insert_or_assign(e.id,std::move(next));
}
void SetAnimationState(Ctx& c,EntityRef e,std::string state,double blend) {
    check(!state.empty() && state.size()<=128,"Animation state must be nonempty and at most 128 bytes");
    blend_duration(blend);
    const auto features=FeatureMetadata(c);
    check(features.contains("3d") && features.at("3d").is_object() && features.at("3d").contains("animation") &&
          features.at("3d").at("animation").is_object(),"Animation state machine is not configured");
    const auto& animation=features.at("3d").at("animation");
    const auto states=animation.value("states",Json::object());
    if(!states.is_object() || !states.contains(state)) throw std::runtime_error("Unknown animation state: "+state);
    const auto& definition=states.at(state);
    const auto clip=definition.is_string() ? definition.get<std::string>() : definition.value("clip",std::string());
    const auto loop=definition.is_object() ? definition.value("loop",true) : true;
    const auto speed_value=definition.is_object() ? definition.value("speed",1.0) : 1.0;
    check(!clip.empty() && std::isfinite(speed_value),"Animation state requires a valid clip and speed");
    PlayAnimationBlended(c,e,clip,loop,speed_value,blend);
}
void StopAnimation(Ctx& c,EntityRef e) { (void)GetEntityMesh(c,e); c.animation.players.erase(e.id); }
void PauseAnimation(Ctx& c,EntityRef e) {
    auto& p=required(c,e); if(p.playing) { p.playing=false; p.paused=true; }
}
void ResumeAnimation(Ctx& c,EntityRef e) {
    auto& p=required(c,e); if(p.paused) { p.playing=true; p.paused=false; }
}
void SetAnimationSpeed(Ctx& c,EntityRef e,double rate) { speed(rate); required(c,e).speed=rate; }
void SetAnimationLoop(Ctx& c,EntityRef e,bool loop) { required(c,e).loop=loop; }
void SetAnimationTime(Ctx& c,EntityRef e,double time) {
    check(std::isfinite(time),"Animation time must be finite");
    auto& p=required(c,e); auto next=p; next.time=std::clamp(time,0.,duration(c,p));
    next.blend_clip.clear(); next.blend_elapsed=next.blend_duration=0;
    validate_pose(c,next); p=std::move(next);
}
double GetAnimationTime(Ctx& c,EntityRef e) { const auto* p=player(c,e); return p ? p->time : 0; }
double GetAnimationProgress(Ctx& c,EntityRef e) {
    const auto* p=player(c,e); return p && duration(c,*p)>0 ? p->time/duration(c,*p) : 0;
}
double GetAnimationDuration(Ctx& c,EntityRef e,std::string clip) {
    const auto& a=asset(c,GetEntityMesh(c,e)); return a.clips()[clip_index(a,clip)].duration;
}
bool IsAnimationPlaying(Ctx& c,EntityRef e) { const auto* p=player(c,e); return p && p->playing; }
bool IsAnimationPaused(Ctx& c,EntityRef e) { const auto* p=player(c,e); return p && p->paused; }
void PruneAnimations(Ctx& c) {
    std::erase_if(c.animation.players,[&](const auto& entry) {
        return !EntityExists(c,{entry.first}) || GetEntityMesh(c,{entry.first})!=entry.second.mesh;
    });
}
void AdvanceAnimations(Ctx& c) {
    check(std::isfinite(c.dt) && c.dt>=0,"Invalid animation delta time");
    PruneAnimations(c);
    for(auto& [id,p]:c.animation.players) {
        if(!p.playing || !IsEntityActive(c,{id}) || c.dt==0 || p.speed==0) continue;
        auto next=p; const double length=duration(c,p); const double previous=p.time;
        const double time=finite(p.time+finite(c.dt*p.speed));
        if(p.loop && length>0) { next.time=std::fmod(time,length); if(next.time<0) next.time+=length; }
        else {
            next.time=std::clamp(time,0.,length);
            if(length==0 || (p.speed>0 && time>=length) || (p.speed<0 && time<=0)) next.playing=false;
        }
        if(!next.blend_clip.empty()) {
            const auto& from=*c.animation.assets.at(next.mesh);
            advance_clock(from,next.blend_index,next.blend_time,next.blend_speed,next.blend_loop,c.dt);
            next.blend_elapsed+=c.dt;
            if(next.blend_elapsed>=next.blend_duration) { next.blend_clip.clear(); next.blend_elapsed=next.blend_duration=0; }
        }
        emit_notifies(c,{id},next,previous,next.time,length);
        validate_pose(c,next); p=std::move(next);
        // Delivery happens at the host boundary, after every player has advanced.
        if(!p.playing) QueueAnimationFinished(c,{id},p.clip);
    }
}
void CloneAnimation(Ctx& c,EntityRef source,EntityRef target) {
    if(const auto* p=player(c,source)) c.animation.players.insert_or_assign(target.id,*p);
}
AnimationPose EntityAnimationPose(const Ctx& c,EntityRef e,const AnimationAsset& a) {
    const auto* p=player(c,e); if(!p) return a.rest_pose();
    auto current=a.sample(clip_index(a,p->clip),p->time);
    if(p->blend_clip.empty() || p->blend_duration<=0) return current;
    auto previous=a.sample(p->blend_index,p->blend_time,p->blend_loop);
    const double weight=std::clamp(p->blend_elapsed/p->blend_duration,0.,1.);
    const auto count=std::min(previous.nodes.size(),current.nodes.size());
    for(std::size_t i=0;i<count;++i) current.nodes[i]=previous.nodes[i]*(1.f-float(weight))+current.nodes[i]*float(weight);
    const auto skins=std::min(previous.skins.size(),current.skins.size());
    for(std::size_t skin=0;skin<skins;++skin) for(std::size_t i=0;i<std::min(previous.skins[skin].size(),current.skins[skin].size());++i)
        current.skins[skin][i]=previous.skins[skin][i]*(1.f-float(weight))+current.skins[skin][i]*float(weight);
    return current;
}
Json AnimationSnapshot(const Ctx& c) {
    Json players=Json::object();
    for(const auto& [id,p]:c.animation.players) {
        if(!EntityExists(c,{id}) || GetEntityMesh(c,{id})!=p.mesh) continue;
        players[id]={{"mesh",p.mesh},{"clip",p.clip},{"time",p.time},{"speed",p.speed},
                     {"loop",p.loop},{"playing",p.playing},{"paused",p.paused}};
        if(!p.blend_clip.empty()) players[id]["blend"]={{"clip",p.blend_clip},{"time",p.blend_time},
            {"speed",p.blend_speed},{"loop",p.blend_loop},{"elapsed",p.blend_elapsed},{"duration",p.blend_duration}};
    }
    return players;
}
void RestoreAnimations(Ctx& c,const Json& saved,const std::filesystem::path& root) {
    check(saved.is_object() && saved.size()<=65536,"Invalid saved animation players");
    PrepareAnimations(c,root);
    for(const auto& [id,value]:saved.items()) {
        check(value.is_object() && (value.size()==7 || value.size()==8),"Invalid saved animation fields");
        const auto mesh=GetEntityMesh(c,{id}); check(value.at("mesh")==mesh,"Saved animation model differs from entity");
        c.animation.players.insert_or_assign(id,select_player(c,{id},FromJson<std::string>(value.at("clip")),
            FromJson<bool>(value.at("loop")),FromJson<double>(value.at("speed"))));
        auto& p=c.animation.players.at(id); const double time=FromJson<double>(value.at("time"));
        check(time>=0 && time<=duration(c,p),"Saved animation time is out of range");
        p.time=time; p.playing=FromJson<bool>(value.at("playing")); p.paused=FromJson<bool>(value.at("paused"));
        check(!(p.playing && p.paused) && (duration(c,p)>0 || (!p.playing && !p.paused)),"Invalid saved animation playback state");
        validate_pose(c,p);
        if(value.contains("blend")) {
            const auto& blend=value.at("blend"); check(blend.is_object() && blend.size()==6,"Invalid saved animation blend");
            const auto& from=asset(c,GetEntityMesh(c,{id})); const auto clip=FromJson<std::string>(blend.at("clip"));
            p.blend_clip=clip; p.blend_index=clip_index(from,clip); p.blend_time=FromJson<double>(blend.at("time"));
            p.blend_speed=FromJson<double>(blend.at("speed")); p.blend_loop=FromJson<bool>(blend.at("loop"));
            p.blend_elapsed=FromJson<double>(blend.at("elapsed")); p.blend_duration=FromJson<double>(blend.at("duration"));
            blend_duration(p.blend_duration); check(p.blend_elapsed>=0 && p.blend_elapsed<=p.blend_duration,"Saved animation blend time is out of range");
            check(p.blend_time>=0 && p.blend_time<=from.clips().at(p.blend_index).duration,"Saved animation blend clip time is out of range");
        }
    }
}
}
