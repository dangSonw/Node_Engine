#pragma once
#include "values.hpp"
#include <filesystem>
#include <functional>
struct SDL_Window;
namespace Rml { class RenderInterface; }
namespace rt {
struct Ctx;
struct SceneSession;
void ConfigureSceneProject(Ctx&,const Json&,const std::filesystem::path&,bool playback=false,
    std::function<void(Ctx&)> bind={},std::function<void(Ctx&)> fixed={});
const Json& CurrentSceneProgram(const Ctx&);
bool ChangeScene(Ctx&,std::string);
bool ReloadScene(Ctx&);
std::string GetActiveScene(Ctx&);
Array<std::string> GetSceneNames(Ctx&);
bool SceneLoadSucceeded(Ctx&);
std::string GetSceneError(Ctx&);
bool SceneChangePending(const Ctx&);
void CancelSceneChange(Ctx&) noexcept;
// Prepare may fail without replacing the world; commit must be a no-throw resource swap.
bool ProcessSceneChange(Ctx&,const std::function<void(const Ctx&)>& prepare={},
    const std::function<void()>& commit={},Rml::RenderInterface* renderer=nullptr,SDL_Window* window=nullptr);
Json SceneSessionSnapshot(const Ctx&);
Ctx SceneCheckpointBindings(const Ctx&,const Json&);
void PrepareSceneAudioOutput(Ctx& candidate,const Ctx& current);
}
