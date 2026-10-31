#include "node_code.hpp"

namespace rt {
void EmbeddedCode(Ctx&) {}
namespace {
using Key = std::tuple<std::string, int, std::string, std::string>;
std::map<Key, NodeCodeHandler>& handlers() {
    static std::map<Key, NodeCodeHandler> result;
    return result;
}
}
void RegisterNodeCode(const std::string& scene, int type, const std::string& node, const std::string& code, NodeCodeHandler handler) {
    handlers().insert_or_assign(Key{scene, type, node, code}, std::move(handler));
}
std::vector<Value> RunNodeCode(Ctx& ctx, int type, const std::string& node,
                              const std::string& code, const std::vector<Value>& args) {
    const auto found = handlers().find(Key{ctx.scene_name.empty() ? "main" : ctx.scene_name, type, node, code});
    if (found == handlers().end())
        throw std::runtime_error("Embedded code for node " + node + " is not compiled. Rebuild this project before Preview.");
    return found->second(ctx, args);
}
}
