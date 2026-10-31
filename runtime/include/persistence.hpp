#pragma once
#include "values.hpp"
#include <filesystem>

namespace rt {
struct Ctx;
struct SaveStorage {
    std::filesystem::path base, directory;
    std::string game, error;
    bool ok = true;
};
bool OpenSaveStorage(Ctx&, std::string game);
bool CreateSaveSlot(Ctx&, std::string slot);
bool DeleteSaveSlot(Ctx&, std::string slot);
bool SaveSlotExists(Ctx&, std::string slot);
Array<std::string> ListSaveSlots(Ctx&);
bool SaveVariable(Ctx&, std::string slot, std::string name);
bool LoadVariable(Ctx&, std::string slot, std::string name);
bool SaveVariables(Ctx&, std::string slot, Array<std::string> names);
bool LoadVariables(Ctx&, std::string slot, Array<std::string> names);
bool SaveJson(Ctx&, std::string slot, std::string key, std::string text);
std::string LoadJson(Ctx&, std::string slot, std::string key);
std::int64_t GetSaveVersion(Ctx&, std::string slot);
bool ValidateSaveData(Ctx&, std::string slot);
// Internal slot transport; checkpoint staging/compatibility belongs to the host.
bool WriteGameCheckpoint(Ctx&,const std::string& slot,const Json& checkpoint);
Json ReadGameCheckpoint(Ctx&,const std::string& slot);
bool SaveOperationSucceeded(Ctx&);
std::string GetSaveError(Ctx&);
}
