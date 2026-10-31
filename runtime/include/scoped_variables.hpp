#pragma once
#include "values.hpp"
#include <map>
#include <string>

namespace rt {
struct Ctx;
using VariableStore = std::map<std::string, Value>;
const Value& GetVariableValue(const Ctx&, const std::string& name);
void SetVariableValue(Ctx&, const std::string& name, Value value);
const Value& GetScopedVariableValue(const Ctx&, const std::string& scope, const std::string& name, EntityRef owner = {});
void SetScopedVariableValue(Ctx&, const std::string& scope, const std::string& name, Value value, EntityRef owner = {});
void LoadVariableState(Ctx&, const Json& scene);
void SnapshotVariableState(const Ctx&, Json& scene);
void InitializeProjectGlobals(Ctx&, const Json& program);
}
