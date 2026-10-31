#pragma once
#include "values.hpp"
#include <filesystem>
#include <memory>
namespace rt {
struct Ctx;
struct AudioSystem;
std::shared_ptr<AudioSystem> CreateAudioSystem(const Json&);
void PrepareAudio(Ctx&,const std::filesystem::path&,bool playback=false);
void AdvanceAudio(Ctx&);
void AdvanceAudio(Ctx&,double seconds);
void PauseAudioOutput(Ctx&,bool);
void EnableAudioOutput(Ctx&);
void BeginAudioCapture(Ctx&,const std::filesystem::path&);
void FinishAudioCapture(Ctx&);
Json AudioAssets(const Ctx&);
Json AudioSnapshot(const Ctx&);
Json AudioCheckpoint(const Ctx&);
void RestoreAudioCheckpoint(Ctx&,const Json&,const std::filesystem::path&,bool playback=false);
// Candidate has no capture. Reuse an existing output; when source has none,
// a newly prepared scene may bring its own device without disturbing the source.
void TransferAudioOutput(Ctx& source,Ctx& candidate);
Json AudioOutputStatus(const Ctx&);
void PlaySound(Ctx&,std::string sound,std::string voice,bool loop,double volume);
void StopSound(Ctx&,std::string voice);
void PauseSound(Ctx&,std::string voice);
void ResumeSound(Ctx&,std::string voice);
bool IsSoundPlaying(Ctx&,std::string voice);
bool IsSoundPaused(Ctx&,std::string voice);
void SetSoundVolume(Ctx&,std::string voice,double);
double GetSoundVolume(Ctx&,std::string voice);
double GetSoundPosition(Ctx&,std::string voice);
double GetSoundDuration(Ctx&,std::string sound);
bool SoundExists(Ctx&,std::string sound);
void StopAllSounds(Ctx&);
void SetMasterVolume(Ctx&,double);
double GetMasterVolume(Ctx&);
}
