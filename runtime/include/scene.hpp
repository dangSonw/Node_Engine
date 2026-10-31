#pragma once
#include "values.hpp"
#include "materials.hpp"
#include "sprites.hpp"
#include <memory>
#include <set>
#include <optional>
#include <glm/mat4x4.hpp>
#include <glm/gtc/quaternion.hpp>
struct ecs_world_t;
namespace rt {
struct Ctx;
struct SceneWorld;
struct Entity { Vec3 position{0}, rotation{0}, scale{1}; bool operator==(const Entity&) const = default; };
struct RenderEntity {
    std::string id, mesh, sorting_layer="default";
    std::int64_t sorting_order=0;
    glm::mat4 matrix;
    std::optional<MaterialParameters> material;
    glm::vec4 uv{1,1,0,0};
    bool sprite=false;
};
struct SpriteStateData {
    std::string asset, state;
    std::int64_t frame=0;
    double elapsed=0;
    bool playing=true;
};
std::shared_ptr<SceneWorld> CreateSceneWorld(const Json&,const Json& identity_checkpoint=Json());
Json SceneIdentityCheckpoint(const Ctx&);
ecs_world_t* NativeWorld(const Ctx&);
std::uint64_t NativeEntity(const Ctx&, const std::string&);
Entity& Find(Ctx&, const std::string&);
bool EntityExists(const Ctx&, EntityRef);
Vec3 GetPosition(Ctx&, EntityRef);
Vec3 GetRotation(Ctx&, EntityRef);
Vec3 GetScale(Ctx&, EntityRef);
void SetPosition(Ctx&, EntityRef, Vec3);
void SetRotation(Ctx&, EntityRef, Vec3);
void SetScale(Ctx&, EntityRef, Vec3);
void Translate(Ctx&, EntityRef, Vec3);
void Rotate(Ctx&, EntityRef, Vec3);
EntityRef SpawnEntity(Ctx&, std::string name, std::string mesh, Vec3 position);
EntityRef CloneEntity(Ctx&, EntityRef, std::string name);
EntityRef InstantiatePrefab(Ctx&, std::string asset, EntityRef parent, Vec3 position);
bool IsPrefabInstance(Ctx&, EntityRef);
std::string GetPrefabAsset(Ctx&, EntityRef);
EntityRef GetPrefabRoot(Ctx&, EntityRef);
EntityRef GetPrefabEntity(Ctx&, EntityRef, std::string local);
void ResetPrefabInstance(Ctx&, EntityRef, bool keep_placement);
void ApplyPrefabOverrides(Ctx&, EntityRef, bool keep_placement);
void DestroyEntity(Ctx&, EntityRef);
EntityRef GetEntityById(Ctx&, std::string);
Array<EntityRef> GetAllEntities(Ctx&);
std::int64_t EntityCount(const Ctx&);
std::uint64_t EntitySerial(const Ctx&);
std::string GetEntityName(Ctx&, EntityRef);
std::string GetEntityMesh(const Ctx&, EntityRef);
void SetEntityName(Ctx&, EntityRef, std::string);
Array<EntityRef> FindEntitiesByName(Ctx&, std::string);
EntityRef GetParent(Ctx&, EntityRef);
void SetParent(Ctx&, EntityRef child, EntityRef parent);
Array<EntityRef> GetChildren(Ctx&, EntityRef);
Vec3 GetWorldPosition(Ctx&, EntityRef);
glm::dmat4 GetWorldMatrix(const Ctx&,EntityRef);
void SetPhysicsWorldPose(Ctx&,EntityRef,Vec3,glm::dquat);
bool IsEntityVisible(Ctx&, EntityRef);
void SetEntityVisibility(Ctx&, EntityRef, bool);
bool IsEntityActive(const Ctx&, EntityRef);
bool GetEntityActiveSelf(Ctx&, EntityRef);
void SetEntityActive(Ctx&, EntityRef, bool);
std::int64_t GetEntityLayer(Ctx&, EntityRef);
void SetEntityLayer(Ctx&, EntityRef, std::int64_t);
Array<EntityRef> FindEntitiesByLayer(Ctx&, std::int64_t, bool);
void AddEntityTag(Ctx&, EntityRef, std::string);
void RemoveEntityTag(Ctx&, EntityRef, std::string);
bool HasEntityTag(Ctx&, EntityRef, std::string);
Array<EntityRef> FindEntitiesByTag(Ctx&, std::string);
std::vector<RenderEntity> RenderEntities(const Ctx&);
Json SceneEntities(const Ctx&);
Json TransformSnapshot(const Ctx&);
Json ComponentDefinitions(const Ctx&);
std::set<std::string> SceneMeshes(const Ctx&);
Json TilemapAssets(const Ctx&);
Json FeatureMetadata(const Ctx&);
Json SpriteStateAssets(const Ctx&);
void SetSpriteState(Ctx&,EntityRef,std::string);
std::string GetSpriteState(Ctx&,EntityRef);
void AdvanceSpriteStates(Ctx&);
void SnapshotPrefabs(const Ctx&, Json& scene, Json& snapshot);
void AddComponent(Ctx&, EntityRef, int);
void RemoveComponent(Ctx&, EntityRef, int);
bool HasComponent(Ctx&, EntityRef, int);
void SetComponentEnabled(Ctx&, EntityRef, int, bool);
bool IsComponentEnabled(Ctx&, EntityRef, int);
Array<EntityRef> FindEntitiesWithComponent(Ctx&, int, bool);
Value ReadComponentProperty(Ctx&, EntityRef, int, int);
void WriteComponentProperty(Ctx&, EntityRef, int, int, Value);
Value DispatchComponent(Ctx&, int, const std::vector<Value>&);
template<class T> T GetComponentProperty(Ctx& c, EntityRef e, int component, int field) {
    return std::get<T>(ReadComponentProperty(c,e,component,field));
}
template<class T> void SetComponentProperty(Ctx& c, EntityRef e, int component, int field, T value) {
    WriteComponentProperty(c,e,component,field,Value{std::move(value)});
}
}
