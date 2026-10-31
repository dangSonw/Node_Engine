#pragma once
#include "values.hpp"
namespace rt {
struct Ctx;
inline constexpr double FixedStep=1.0/60.0;
void SetTimeScale(Ctx&,double);
void PauseWorld(Ctx&);
void ResumeWorld(Ctx&);
bool IsWorldPaused(Ctx&);
double GetTimeScale(Ctx&);
double UnscaledDeltaTime(Ctx&);
double RealTime(Ctx&);
double FixedDeltaTime();
void BeginGameFrame(Ctx&,double elapsed,double step);
inline void BeginGameFrame(Ctx& c,double elapsed) { BeginGameFrame(c,elapsed,elapsed); }
void EndGameFrame(Ctx&);
void ValidateFrameEvents(const Json& program);
}
