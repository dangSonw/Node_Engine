#pragma once
#include "animation_asset.hpp"
#include "values.hpp"
#include <map>
namespace rt {
struct Ctx;
struct AnimationPlayer {
    std::string mesh,clip;
    size_t index=0;
    double time=0,speed=1;
    bool loop=true,playing=true,paused=false;
    // Optional transition from the previous clip. Empty blend_clip means the
    // player is using the legacy single-clip path.
    std::string blend_clip;
    size_t blend_index=0;
    double blend_time=0,blend_speed=1,blend_elapsed=0,blend_duration=0;
    bool blend_loop=true;
};
struct AnimationScene {
    std::filesystem::path root;
    std::map<std::string,std::shared_ptr<const AnimationAsset>> assets;
    std::map<std::string,AnimationPlayer> players;
};
void PrepareAnimations(Ctx&,const std::filesystem::path&);
void AdvanceAnimations(Ctx&);
void PruneAnimations(Ctx&);
void CloneAnimation(Ctx&,EntityRef,EntityRef);
Json AnimationSnapshot(const Ctx&);
void RestoreAnimations(Ctx&,const Json&,const std::filesystem::path&);
AnimationPose EntityAnimationPose(const Ctx&,EntityRef,const AnimationAsset&);
Array<std::string> GetAnimationClips(Ctx&,EntityRef);
void PlayAnimation(Ctx&,EntityRef,std::string,bool,double);
void PlayAnimationBlended(Ctx&,EntityRef,std::string,bool,double,double);
void SetAnimationState(Ctx&,EntityRef,std::string,double);
void StopAnimation(Ctx&,EntityRef);
void PauseAnimation(Ctx&,EntityRef);
void ResumeAnimation(Ctx&,EntityRef);
void SetAnimationSpeed(Ctx&,EntityRef,double);
void SetAnimationLoop(Ctx&,EntityRef,bool);
void SetAnimationTime(Ctx&,EntityRef,double);
double GetAnimationTime(Ctx&,EntityRef);
double GetAnimationProgress(Ctx&,EntityRef);
double GetAnimationDuration(Ctx&,EntityRef,std::string);
bool IsAnimationPlaying(Ctx&,EntityRef);
bool IsAnimationPaused(Ctx&,EntityRef);
}
