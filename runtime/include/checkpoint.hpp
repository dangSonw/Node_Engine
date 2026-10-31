#pragma once
#include "values.hpp"
#include <filesystem>
#include <functional>
struct SDL_Window;
namespace Rml { class RenderInterface; }
namespace rt {
struct Ctx;
struct GamePersistence;
void ConfigureGamePersistence(Ctx&,const Json& program,const std::filesystem::path& root);
void VerifyGameResources(const Ctx&);
bool SaveGame(Ctx&,std::string slot);
bool LoadGame(Ctx&,std::string slot);
bool GameSavePending(Ctx&);
void CancelGamePersistence(Ctx&) noexcept;
// Returns true only when a load commits; queues the accepted request's result.
// Hosts clear old input after a committed load, then call DrainEvents once.
bool ProcessGamePersistence(Ctx&,const std::function<void(const Ctx&)>& prepare={},
    Rml::RenderInterface* renderer=nullptr,SDL_Window* window=nullptr,const std::function<void()>& commit={});
// Strict initial compatibility: program IR, runtime implementation and the full
// project assets directory plus scene/prefab models and their external dependencies.
// Paths are relative so relocated packages still match.
Json GameProgramIdentity(const Json& program,const std::filesystem::path& root);
// Internal host API. Identity is supplied by the current program, never executed
// from a save. Stage owns an independent world/mixer/UI without live host output.
Json GameCheckpoint(const Ctx&,const Json& identity);
Ctx StageGameCheckpoint(const Ctx& current,const Json& identity,const Json& saved,
    const std::filesystem::path& root,Rml::RenderInterface* renderer=nullptr,SDL_Window* window=nullptr);
// Call only after any host GPU/resource staging has succeeded at a frame boundary.
void CommitGameCheckpoint(Ctx& current,Ctx&& candidate);
}
