#pragma once
#include "values.hpp"
#include <set>

namespace rt {
// Build the entire transaction before mutating the live Flecs world.
Json PlanPrefabApply(const Json& scene, const std::string& root, bool keep_placement,
                     const std::set<std::string>& reserved, std::uint64_t serial);
}
