#pragma once
#include "runtime.hpp"
#include <functional>
#include <tuple>

namespace rt {
void EmbeddedCode(Ctx& ctx);
using NodeCodeHandler = std::function<std::vector<Value>(Ctx&, const std::vector<Value>&)>;
void RegisterNodeCode(const std::string& scene, int type, const std::string& node, const std::string& code, NodeCodeHandler handler);
std::vector<Value> RunNodeCode(Ctx& ctx, int type, const std::string& node,
                              const std::string& code, const std::vector<Value>& args);
}
