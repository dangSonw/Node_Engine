#define GLM_ENABLE_EXPERIMENTAL
#include "runtime.hpp"
#include "prefab_edits.hpp"
#include <flecs.h>
#include <glm/gtc/matrix_transform.hpp>
#include <glm/gtx/euler_angles.hpp>
#include <regex>
#include <deque>
#include <exception>

namespace rt {
namespace {
struct Identity { std::string id, name; };
struct Mesh { std::string asset; bool visible=true; bool operator==(const Mesh&) const = default; };
struct Tags { std::set<std::string> values; bool operator==(const Tags&) const = default; };
struct Activity { bool active=true; std::int64_t layer=0; bool operator==(const Activity&) const = default; };
struct RigidBodyConfig { Json value=nullptr; bool operator==(const RigidBodyConfig&) const = default; };
RigidBodyConfig ReadBodyConfig(const Json& value) {
    if(!value.is_null()) (void)ReadAuthoredBody(value);
    return {value};
}
struct ComponentData { bool enabled=true; std::map<int,Value> properties; };
struct ComponentField { std::string type; Value initial; };
struct ComponentSchema { ecs_entity_t entity; Json definition; std::map<int,ComponentField> fields; };
struct PrefabTemplate { std::string asset, local; };
struct PrefabLink { std::string asset, local, root; };
struct PrefabAsset {
    std::string root;
    std::map<std::string,ecs_entity_t> nodes;
    std::map<std::string,std::string> parents, names;
    int depth=1;
};
struct PrefabInstance {
    std::string asset;
    std::map<std::string,std::string> mapping, retired;
    Json component_overrides=Json::object();
};
struct DeferredSceneEdit { int kind; EntityRef entity; bool keep; std::string origin; };
void Text(const std::string& text, std::size_t limit, const char* field) {
    CheckValue(text);
    if(text.empty() || text.size()>limit || text.find_first_not_of(" \t\r\n")==std::string::npos ||
       std::any_of(text.begin(),text.end(),[](unsigned char c){return c<32 || c==127;}))
        throw std::runtime_error(std::string("Invalid ")+field);
}
void ValidateFeatureMetadata(const Json& features) {
    if(!features.is_object()) throw std::runtime_error("Scene features must be an object");
    const auto& three_d=features.value("3d",Json::object());
    if(!three_d.is_object()) throw std::runtime_error("Scene 3d features must be an object");
    if(three_d.contains("pbr")) {
        const auto& pbr=three_d.at("pbr");
        if(!pbr.is_object()) throw std::runtime_error("PBR feature must be an object");
        for(const auto* key:{"metallic","roughness"}) if(pbr.contains(key) &&
            (!pbr.at(key).is_number() || !std::isfinite(pbr.at(key).get<double>()) || pbr.at(key)<0 || pbr.at(key)>1))
            throw std::runtime_error("PBR metallic/roughness must be between 0 and 1");
        for(const auto* key:{"base_color","emission"}) if(pbr.contains(key)) {
            const auto& color=pbr.at(key); const std::size_t expected=std::string(key)=="base_color" ? 4 : 3;
            if(!color.is_array() || color.size()!=expected) throw std::runtime_error("Invalid PBR color vector");
            for(const auto& channel:color) if(!channel.is_number() || !std::isfinite(channel.get<double>()) || channel<0 || (std::string(key)=="base_color" && channel>1))
                throw std::runtime_error("Invalid PBR color channel");
        }
    }
    if(three_d.contains("lights")) {
        const auto& lights=three_d.at("lights"); if(!lights.is_array() || lights.size()>1024) throw std::runtime_error("Invalid lights feature");
        for(const auto& light:lights) {
            if(!light.is_object() || !std::set<std::string>{"point","directional","spot"}.contains(light.value("kind",std::string{})))
                throw std::runtime_error("Unsupported light kind");
            if(light.contains("intensity") && (!light.at("intensity").is_number() || light.at("intensity")<0)) throw std::runtime_error("Invalid light intensity");
            if(light.contains("range") && (!light.at("range").is_number() || light.at("range")<=0)) throw std::runtime_error("Invalid light range");
            for(const auto* key:{"position","direction"}) if(light.contains(key)) {
                const auto& vector=light.at(key);
                if(!vector.is_array() || vector.size()!=3) throw std::runtime_error("Light position/direction must be a vec3");
                for(const auto& value:vector) if(!value.is_number() || !std::isfinite(value.get<double>()))
                    throw std::runtime_error("Light position/direction must be finite");
            }
        }
    }
    if(three_d.contains("shader_graph")) {
        const auto& graph=three_d.at("shader_graph"); if(!graph.is_object() || !graph.value("nodes",Json::array()).is_array() || !graph.value("edges",Json::array()).is_array())
            throw std::runtime_error("Invalid Shader Graph");
        std::set<std::string> nodes;
        for(const auto& node:graph.at("nodes")) if(!node.is_object() || !node.contains("id") || !node.at("id").is_string() || !nodes.insert(node.at("id").get<std::string>()).second)
            throw std::runtime_error("Shader Graph node IDs must be unique");
        std::map<std::string,std::vector<std::string>> outgoing;
        for(const auto& edge:graph.at("edges")) {
            if(!edge.is_array() || edge.size()!=2 || !edge.at(0).is_string() || !edge.at(1).is_string() || !nodes.contains(edge.at(0)) || !nodes.contains(edge.at(1)))
                throw std::runtime_error("Shader Graph edge references an unknown node");
            outgoing[edge.at(0)].push_back(edge.at(1).get<std::string>());
        }
        std::set<std::string> visiting,visited;
        std::function<void(const std::string&)> visit=[&](const std::string& node) {
            if(visiting.contains(node)) throw std::runtime_error("Shader Graph contains a cycle");
            if(!visited.insert(node).second) return;
            visiting.insert(node); for(const auto& target:outgoing[node]) visit(target); visiting.erase(node);
        };
        for(const auto& node:nodes) visit(node);
    }
    if(three_d.contains("animation")) {
        const auto& animation=three_d.at("animation");
        if(!animation.is_object()) throw std::runtime_error("Animation feature must be an object");
        const auto notifies=animation.value("notifies",Json::array());
        if(!notifies.is_array() || notifies.size()>4096) throw std::runtime_error("Invalid animation notify list");
        for(const auto& notify:notifies) {
            if(!notify.is_object() || !notify.contains("clip") || !notify.contains("name") || !notify.contains("time") ||
               !notify.at("clip").is_string() || !notify.at("name").is_string() || !notify.at("time").is_number() ||
               !std::isfinite(notify.at("time").get<double>()) || notify.at("time")<0)
                throw std::runtime_error("Invalid animation notify");
            Text(notify.at("clip").get<std::string>(),512,"animation notify clip");
            Text(notify.at("name").get<std::string>(),512,"animation notify name");
        }
        if(animation.contains("states")) {
            const auto& states=animation.at("states");
            if(!states.is_object() || states.empty() || states.size()>256) throw std::runtime_error("Animation states must be a nonempty object");
            for(const auto& [name,definition]:states.items()) {
                Text(name,128,"animation state name");
                if(definition.is_string()) Text(definition.get<std::string>(),512,"animation state clip");
                else if(definition.is_object()) {
                    if(!definition.contains("clip") || !definition.at("clip").is_string() ||
                       (definition.contains("loop") && !definition.at("loop").is_boolean()) ||
                       (definition.contains("speed") && !definition.at("speed").is_number()))
                        throw std::runtime_error("Invalid animation state definition");
                    Text(definition.at("clip").get<std::string>(),512,"animation state clip");
                    if(!std::isfinite(definition.value("speed",1.0))) throw std::runtime_error("Animation state speed must be finite");
                } else throw std::runtime_error("Animation state must be a clip string or object");
            }
        }
    }
    const auto& gameplay=features.value("gameplay",Json::object());
    if(!gameplay.is_object()) throw std::runtime_error("Gameplay features must be an object");
    if(gameplay.contains("navigation")) {
        const auto& nav=gameplay.at("navigation"); const auto grid=nav.value("grid",Json::array());
        if(!nav.is_object() || !grid.is_array() || grid.size()!=2 || !grid.at(0).is_number_integer() || !grid.at(1).is_number_integer() || grid.at(0)<1 || grid.at(1)<1 || grid.at(0)>4096 || grid.at(1)>4096)
            throw std::runtime_error("Invalid navigation grid");
    }
    if(gameplay.contains("replication") && (!gameplay.at("replication").is_object() || !std::set<std::string>{"server","owner","client"}.contains(gameplay.at("replication").value("authority",std::string{}))))
        throw std::runtime_error("Invalid replication authority");
    if(gameplay.contains("autosave") && (!gameplay.at("autosave").is_object() || !gameplay.at("autosave").at("interval").is_number() || gameplay.at("autosave").at("interval")<=0))
        throw std::runtime_error("Invalid autosave interval");
}
}
struct SceneWorld {
    flecs::world world;
    // Lookup contains handles only: component storage belongs exclusively to Flecs.
    std::map<std::string,ecs_entity_t> index;
    std::set<std::string> used, assets;
    std::uint64_t serial=0;
    ecs_entity_t scene=0;
    std::string active_camera;
    MaterialLibrary materials;
    SpriteLibrary sprites;
    std::map<int,ComponentSchema> components;
    std::map<std::string,PrefabAsset> prefabs;
    std::map<std::string,PrefabInstance> instances;
    std::map<std::string,std::pair<std::string,std::int64_t>> render_order;
    Json tilemaps=Json::array();
    Json sprite_state_assets=Json::array();
    std::map<std::string,SpriteStateData> sprite_states;
    // Optional pipeline metadata is authored once and carried through the
    // native scene snapshot so headless, preview and exported hosts agree on
    // the same 2D/3D/game/editor contracts.
    Json features=Json::object();
    Json prefab_assets=Json::array(), prefab_templates=Json::array();
    std::set<std::string> destroying;
    bool editing_destruction=false, flushing_edits=false;
    std::deque<DeferredSceneEdit> deferred_edits;
    SceneWorld() {
        world.component<Entity>("Transform").add(flecs::OnInstantiate,flecs::Inherit);
        world.component<Identity>("Identity").add(flecs::OnInstantiate,flecs::DontInherit);
        world.component<Mesh>("Mesh").add(flecs::OnInstantiate,flecs::Inherit);
        world.component<Tags>("Tags").add(flecs::OnInstantiate,flecs::Inherit);
        world.component<Activity>("Activity").add(flecs::OnInstantiate,flecs::Inherit);
        world.component<Camera>("Camera").add(flecs::OnInstantiate,flecs::Inherit);
        world.component<MaterialBinding>("Material").add(flecs::OnInstantiate,flecs::Inherit);
        world.component<SpriteBinding>("Sprite").add(flecs::OnInstantiate,flecs::Inherit);
        world.component<RigidBodyConfig>("RigidBodyConfig").add(flecs::OnInstantiate,flecs::Inherit);
        // Mutable user data follows Flecs' default Override policy. References
        // in these owned copies are remapped for each instance after IsA.
        world.component<ComponentData>("UserComponentData");
        world.component<PrefabTemplate>("PrefabTemplate").add(flecs::OnInstantiate,flecs::DontInherit);
        world.component<PrefabLink>("PrefabLink").add(flecs::OnInstantiate,flecs::DontInherit);
        scene=world.entity().id();
    }
};
static SceneWorld& World(const Ctx& c) {
    if(!c.world) throw std::runtime_error("No scene loaded");
    return *c.world;
}
namespace {
struct DestructionEdit {
    SceneWorld& world;
    int exceptions=std::uncaught_exceptions();
    explicit DestructionEdit(Ctx& c):world(World(c)) {
        if(world.editing_destruction) throw std::runtime_error("Nested destructive scene edit must be deferred");
        world.editing_destruction=true;
    }
    ~DestructionEdit() {
        world.editing_destruction=false; world.destroying.clear();
        if(std::uncaught_exceptions()>exceptions) world.deferred_edits.clear();
    }
};
bool DeferSceneEdit(Ctx& c,int kind,EntityRef entity,bool keep=true) {
    auto& w=World(c);
    if(!w.editing_destruction) return false;
    if(kind==0 && w.destroying.contains(entity.id)) return true;
    if(w.deferred_edits.size()>=4096) throw std::runtime_error("Too many deferred scene edits (4096)");
    w.deferred_edits.push_back({kind,std::move(entity),keep,c.current_node}); return true;
}
void FlushSceneEdits(Ctx& c) {
    auto& w=World(c);
    if(w.flushing_edits || w.editing_destruction) return;
    struct Guard { bool& flag; ~Guard(){flag=false;} } guard{w.flushing_edits}; w.flushing_edits=true;
    const auto origin=c.current_node;
    try {
        while(!w.deferred_edits.empty()) {
            auto edit=std::move(w.deferred_edits.front()); w.deferred_edits.pop_front(); Tick(c,edit.origin);
            if(!EntityExists(c,edit.entity)) continue;
            if(edit.kind==0) DestroyEntity(c,edit.entity);
            else if(edit.kind==1) ResetPrefabInstance(c,edit.entity,edit.keep);
            else ApplyPrefabOverrides(c,edit.entity,edit.keep);
        }
    } catch(...) { w.deferred_edits.clear(); throw; }
    c.current_node=origin;
}
}
ecs_world_t* NativeWorld(const Ctx& c) { return World(c).world.c_ptr(); }
std::uint64_t NativeEntity(const Ctx& c,const std::string& id) {
    auto& w=World(c);
    if(id.empty()) return w.scene;
    auto found=w.index.find(id);
    if(found==w.index.end()) throw std::runtime_error("Missing entity: "+id);
    return found->second;
}
static flecs::entity Handle(const Ctx& c,const std::string& id) {
    if(id.empty()) throw std::runtime_error("Missing entity: ");
    return World(c).world.entity(NativeEntity(c,id));
}
static flecs::entity Insert(SceneWorld& w,const std::string& id,const std::string& name,Entity transform,Mesh mesh,Tags tags,Activity activity={},Camera camera={},MaterialBinding material={},SpriteBinding sprite={},RigidBodyConfig body={}) {
    Text(id,128,"entity ID"); Text(name,512,"entity name");
    if(w.index.size()>=65536) throw std::runtime_error("At most 65536 entities are allowed");
    if(w.index.contains(id)) throw std::runtime_error("Duplicate entity: "+id);
    auto e=w.world.entity().set<Identity>({id,name}).set<Entity>(transform).set<Mesh>(mesh).set<Tags>(tags).set<Activity>(activity).set<Camera>(camera).set<MaterialBinding>(material).set<SpriteBinding>(sprite);
    e.set<RigidBodyConfig>(body);
    w.index.emplace(id,e.id());
    return e;
}
static int SchemaId(const Json& value,int limit) {
    if(!value.is_number_integer() || value<1 || value>limit) throw std::runtime_error("Invalid component/property ID");
    return value.get<int>();
}
static void CheckCamera(const Camera& camera) {
    if(!std::isfinite(camera.fov) || camera.fov<1 || camera.fov>179 ||
       !std::isfinite(camera.size) || camera.size<=0 || camera.size>1e9 ||
       !std::isfinite(camera.near_clip) || !std::isfinite(camera.far_clip) ||
       camera.near_clip<=0 || camera.near_clip>=camera.far_clip || camera.far_clip>1e9)
        throw std::runtime_error("Invalid camera FOV, size or clipping planes");
}
static Camera ReadCameraJson(const Json& value) {
    Camera camera;
    if(value.is_null()) return camera;
    if(!value.is_object() || value.size()!=5 || !value.contains("projection") ||
       !value.contains("fov") || !value.contains("size") || !value.contains("near") || !value.contains("far"))
        throw std::runtime_error("Camera requires projection, fov, size, near and far");
    const auto projection=value.at("projection").get<std::string>();
    if(projection!="perspective" && projection!="orthographic") throw std::runtime_error("Unknown camera projection");
    camera.present=true; camera.orthographic=projection=="orthographic";
    camera.fov=FromJson<double>(value.at("fov")); camera.size=FromJson<double>(value.at("size"));
    camera.near_clip=FromJson<double>(value.at("near")); camera.far_clip=FromJson<double>(value.at("far"));
    CheckCamera(camera); return camera;
}
static Json CameraJson(const Camera& camera) {
    return {{"projection",camera.orthographic ? "orthographic" : "perspective"},
        {"fov",camera.fov},{"size",camera.size},{"near",camera.near_clip},{"far",camera.far_clip}};
}
static Json DefaultProperty(const std::string& type) {
    if(type.starts_with("array<")) return Json::array();
    if(type.starts_with("map<")) return Json::object();
    if(type=="bool") return false;
    if(type=="string" || type=="entity") return "";
    if(type=="vec2") return Json::array({0.,0.});
    if(type=="vec3") return Json::array({0.,0.,0.});
    if(type=="vec4") return Json::array({0.,0.,0.,0.});
    if(type=="quat") return Json::array({0.,0.,0.,1.});
    if(type=="mat4") return Json::array({1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.});
    return 0;
}
static ComponentSchema& Component(Ctx& c,int id) {
    auto& schemas=World(c).components;
    auto found=schemas.find(id);
    if(found==schemas.end()) throw std::runtime_error("Unknown component definition: "+std::to_string(id));
    return found->second;
}
static const ComponentData& Data(Ctx& c,EntityRef id,int component) {
    auto e=Handle(c,id.id); auto handle=Component(c,component).entity;
    if(!e.has<ComponentData>(handle)) throw std::runtime_error("Entity lacks component: "+std::to_string(component));
    return e.get<ComponentData>(handle);
}
static void LoadComponentSchemas(SceneWorld& world,const Json& definitions) {
    if(!definitions.is_array() || definitions.size()>256) throw std::runtime_error("Invalid component definitions");
    static const std::regex identifier("[A-Za-z_][A-Za-z0-9_]{0,63}");
    for(const auto& definition:definitions) {
        const auto id=SchemaId(definition.at("id"),3999);
        if(world.components.contains(id)) throw std::runtime_error("Duplicate component ID");
        Text(definition.at("name").get<std::string>(),512,"component name");
        const auto& fields=definition.at("properties");
        if(!fields.is_array() || fields.size()>32) throw std::runtime_error("Invalid component properties");
        ComponentSchema schema{world.world.entity().id(),definition,{}};
        std::set<std::string> names;
        for(const auto& field:fields) {
            int fid=SchemaId(field.at("id"),32);
            auto name=field.at("name").get<std::string>();
            if(schema.fields.contains(fid) || !std::regex_match(name,identifier) || !names.insert(name).second)
                throw std::runtime_error("Invalid or duplicate component property");
            auto type=field.at("type").get<std::string>();
            schema.fields.emplace(fid,ComponentField{type,ValueFromJson(type,field.value("default",DefaultProperty(type)))});
        }
        world.components.emplace(id,std::move(schema));
    }
}
static int KeyId(const std::string& key,int limit) {
    if(key.empty() || key.size()>4 || !std::all_of(key.begin(),key.end(),[](char ch){return ch>='0' && ch<='9';}))
        throw std::runtime_error("Invalid component/property ID key");
    int value=std::stoi(key);
    if(value<1 || value>limit || std::to_string(value)!=key) throw std::runtime_error("Invalid component/property ID key");
    return value;
}
static std::map<ecs_entity_t,ComponentData> ReadPrefabComponents(SceneWorld& w,const Json& instances) {
    if(!instances.is_object()) throw std::runtime_error("Prefab components must be an object");
    std::map<ecs_entity_t,ComponentData> result;
    for(const auto& [key,instance]:instances.items()) {
        int cid=KeyId(key,3999);
        if(!w.components.contains(cid)) throw std::runtime_error("Unknown prefab component");
        const auto& schema=w.components.at(cid);
        ComponentData data; data.enabled=instance.value("enabled",true);
        for(const auto& [fid,field]:schema.fields) data.properties.emplace(fid,field.initial);
        const auto fields=instance.value("properties",Json::object());
        if(!fields.is_object()) throw std::runtime_error("Prefab component properties must be an object");
        for(const auto& [key,value]:fields.items()) {
            int fid=KeyId(key,32);
            if(!schema.fields.contains(fid)) throw std::runtime_error("Unknown prefab component property");
            data.properties[fid]=ValueFromJson(schema.fields.at(fid).type,value);
        }
        result.emplace(schema.entity,std::move(data));
    }
    return result;
}
static void RemapPrefabData(ComponentData& data,const std::map<std::string,std::string>& mapping) {
    auto remap=[&](EntityRef& ref) {
        if(ref.id.empty()) return;
        auto found=mapping.find(ref.id);
        if(found==mapping.end()) throw std::runtime_error("Prefab reference targets missing local entity: "+ref.id);
        ref.id=found->second;
    };
    for(auto& [_,value]:data.properties) std::visit([&](auto& v) {
        using T=std::decay_t<decltype(v)>;
        if constexpr(std::is_same_v<T,EntityRef>) remap(v);
        else if constexpr(std::is_same_v<T,Array<EntityRef>>) for(auto& ref:v) remap(ref);
        else if constexpr(std::is_same_v<T,Map<EntityRef>>) for(auto& [_,ref]:v) remap(ref);
    },value);
}
template<class T> static void TemplateValue(flecs::entity e,flecs::entity base,const T& value) {
    if(!base.id() || !(base.get<T>()==value)) e.set<T>(value);
}
static void LoadPrefabAssets(SceneWorld& w,const Json& scene) {
    w.prefab_assets=scene.value("prefab_assets",Json::array());
    w.prefab_templates=scene.value("prefab_templates",Json::array());
    if(!w.prefab_assets.is_array() || w.prefab_assets.size()>1024 || !w.prefab_templates.is_array() ||
       w.prefab_templates.size()!=w.prefab_assets.size()) throw std::runtime_error("Invalid native prefab library; compile authored assets first");
    std::set<std::string> sources;
    for(const auto& source:w.prefab_assets) {
        auto id=source.at("id").get<std::string>(); Text(id,48,"prefab ID");
        if(!sources.insert(id).second) throw std::runtime_error("Duplicate prefab asset");
    }
    std::size_t total=0;
    for(const auto& definition:w.prefab_templates) {
        auto aid=definition.at("id").get<std::string>();
        if(!sources.contains(aid) || w.prefabs.contains(aid)) throw std::runtime_error("Invalid prefab template asset ID");
        PrefabAsset prefab; prefab.root=definition.at("root").get<std::string>();
        const auto& entities=definition.at("entities"); const auto bases=definition.value("bases",Json::object());
        if(!entities.is_array() || entities.empty() || (total+=entities.size())>65536 || !bases.is_object())
            throw std::runtime_error("Invalid prefab templates or template entity limit exceeded");
        for(const auto& item:entities) {
            auto local=item.at("id").get<std::string>(); Text(local,128,"prefab local ID");
            if(prefab.nodes.contains(local)) throw std::runtime_error("Duplicate prefab local ID");
            auto name=item.value("name",local); Text(name,512,"prefab entity name");
            auto base=w.world.entity(0);
            if(bases.contains(local)) {
                const auto& binding=bases.at(local);
                auto asset=binding.at("asset").get<std::string>(), source=binding.at("local").get<std::string>();
                if(!w.prefabs.contains(asset) || !w.prefabs.at(asset).nodes.contains(source))
                    throw std::runtime_error("Missing or unordered prefab base template");
                base=w.world.entity(w.prefabs.at(asset).nodes.at(source));
            }
            auto e=w.world.prefab().set<PrefabTemplate>({aid,local});
            if(base.id()) e.is_a(base);
            TemplateValue(e,base,Entity{vec_from_json(item.at("position")),vec_from_json(item.at("rotation")),vec_from_json(item.at("scale"))});
            Mesh mesh{item.value("mesh",std::string{}),item.value("visible",true)};
            TemplateValue(e,base,mesh);
            if(!mesh.asset.empty()) w.assets.insert(mesh.asset);
            Tags tags;
            const auto values=item.value("tags",Json::array());
            if(!values.is_array() || values.size()>256) throw std::runtime_error("Invalid prefab tags");
            for(const auto& value:values) {
                auto tag=value.get<std::string>(); Text(tag,128,"prefab tag");
                if(!tags.values.insert(tag).second) throw std::runtime_error("Duplicate prefab tag");
            }
            TemplateValue(e,base,tags);
            const auto layer=item.value("layer",Json(0));
            if(!layer.is_number_integer() || layer<0 || layer>31) throw std::runtime_error("Invalid prefab layer");
            TemplateValue(e,base,Activity{item.value("active",true),layer.get<std::int64_t>()});
            TemplateValue(e,base,ReadCameraJson(item.value("camera",Json())));
            TemplateValue(e,base,ReadMaterialBinding(item.value("material",Json()),w.materials));
            TemplateValue(e,base,ReadSpriteBinding(item.value("sprite",Json()),w.sprites));
            TemplateValue(e,base,ReadBodyConfig(item.value("rigid_body",Json())));
            const auto components=ReadPrefabComponents(w,item.value("components",Json::object()));
            for(const auto& [_,schema]:w.components) {
                if(components.contains(schema.entity)) e.set<ComponentData>(schema.entity,components.at(schema.entity));
                else e.remove<ComponentData>(schema.entity);
            }
            prefab.nodes.emplace(local,e.id());
            prefab.parents.emplace(local,item.value("parent",std::string{}));
            prefab.names.emplace(local,name);
        }
        if(!prefab.nodes.contains(prefab.root) || !prefab.parents.at(prefab.root).empty())
            throw std::runtime_error("Prefab requires its root");
        std::map<std::string,std::string> identity;
        for(const auto& [local,_]:prefab.nodes) identity.emplace(local,local);
        for(const auto& [local,handle]:prefab.nodes) {
            std::set<std::string> visited;
            for(auto current=local; !current.empty(); current=prefab.parents.at(current)) {
                if(!prefab.nodes.contains(current) || !visited.insert(current).second || visited.size()>256)
                    throw std::runtime_error("Invalid prefab hierarchy or hierarchy exceeds 256 levels");
                if(current!=prefab.root && prefab.parents.at(current).empty()) throw std::runtime_error("Disconnected prefab root");
            }
            prefab.depth=std::max(prefab.depth,static_cast<int>(visited.size()));
            auto e=w.world.entity(handle);
            for(const auto& [_,schema]:w.components) if(e.has<ComponentData>(schema.entity)) {
                auto data=e.get<ComponentData>(schema.entity); RemapPrefabData(data,identity);
            }
        }
        for(const auto& [local,_]:bases.items()) if(!prefab.nodes.contains(local)) throw std::runtime_error("Unknown prefab base local ID");
        w.prefabs.emplace(aid,std::move(prefab));
    }
}
template<class T> static void RestoreInheritance(flecs::entity e,flecs::entity base,const Json* owned,const char* name) {
    const bool equal=e.get<T>()==base.get<T>();
    if(owned) {
        if(std::find(owned->begin(),owned->end(),name)!=owned->end()) return;
        if(!equal) throw std::runtime_error(std::string("Inherited prefab value differs from its template: ")+name);
    }
    if(equal) e.remove<T>();
}
static void LoadPrefabInstances(Ctx& c,const Json& scene) {
    auto& w=World(c); const auto records=scene.value("prefab_instances",Json::array());
    if(!records.is_array() || records.size()>65536) throw std::runtime_error("Invalid prefab instances");
    std::set<std::string> claimed;
    for(const auto& record:records) {
        const auto aid=record.at("prefab").get<std::string>(), root=record.at("root").get<std::string>();
        if(!w.prefabs.contains(aid) || !w.index.contains(root) || w.instances.contains(root)) throw std::runtime_error("Missing prefab instance root or asset");
        const auto& prefab=w.prefabs.at(aid);
        const auto& entries=record.at("mapping");
        if(!entries.is_object() || entries.size()!=prefab.nodes.size()) throw std::runtime_error("Incomplete prefab instance mapping");
        PrefabInstance instance{aid,{}, {}};
        for(const auto& [local,value]:entries.items()) {
            auto id=value.get<std::string>(); Text(id,128,"prefab instance entity ID");
            if(!prefab.nodes.contains(local) || !claimed.insert(id).second) throw std::runtime_error("Overlapping or invalid prefab instance mapping");
            instance.mapping.emplace(local,id); w.used.insert(id);
        }
        if(instance.mapping.at(prefab.root)!=root) throw std::runtime_error("Incorrect prefab instance root mapping");
        const auto retired=record.value("retired",Json::object());
        if(!retired.is_object() || retired.size()>65536) throw std::runtime_error("Invalid retired prefab mapping");
        for(const auto& [local,value]:retired.items()) {
            Text(local,128,"retired prefab local ID");
            auto id=value.get<std::string>(); Text(id,128,"retired prefab entity ID");
            if(instance.mapping.contains(local) || w.index.contains(id) || !claimed.insert(id).second)
                throw std::runtime_error("Overlapping or live retired prefab ID");
            instance.retired.emplace(local,id); w.used.insert(id);
        }
        const auto ownership=record.value("owned_components",Json::object());
        if(!ownership.is_object()) throw std::runtime_error("Invalid owned prefab components");
        for(const auto& [local,names]:ownership.items()) {
            if(!instance.mapping.contains(local) || !names.is_array()) throw std::runtime_error("Invalid owned prefab component list");
            std::set<std::string> seen;
            for(const auto& name:names) {
                const auto text=name.get<std::string>();
                if((text!="transform" && text!="mesh" && text!="tags" && text!="activity" && text!="camera" && text!="material" && text!="sprite" && text!="rigid_body") || !seen.insert(text).second)
                    throw std::runtime_error("Invalid owned prefab component name");
            }
        }
        for(const auto& [local,id]:instance.mapping) {
            if(!w.index.contains(id)) continue; // Deleted members retain tombstone IDs.
            auto e=Handle(c,id), base=w.world.entity(prefab.nodes.at(local));
            std::set<ecs_entity_t> owned_data;
            for(const auto& [_,schema]:w.components) if(e.has<ComponentData>(schema.entity)) owned_data.insert(schema.entity);
            e.is_a(base).set<PrefabLink>({aid,local,root});
            // IsA auto-copies mutable component pairs. A saved removal must stay removed.
            for(const auto& [_,schema]:w.components) if(!owned_data.contains(schema.entity)) e.remove<ComponentData>(schema.entity);
            const Json* owned=ownership.contains(local) ? &ownership.at(local) : nullptr;
            RestoreInheritance<Entity>(e,base,owned,"transform");
            RestoreInheritance<Mesh>(e,base,owned,"mesh");
            RestoreInheritance<Tags>(e,base,owned,"tags");
            RestoreInheritance<Activity>(e,base,owned,"activity");
            RestoreInheritance<Camera>(e,base,owned,"camera");
            RestoreInheritance<MaterialBinding>(e,base,owned,"material");
            RestoreInheritance<SpriteBinding>(e,base,owned,"sprite");
            RestoreInheritance<RigidBodyConfig>(e,base,owned,"rigid_body");
        }
        instance.component_overrides=record.value("component_overrides",Json::object());
        if(!instance.component_overrides.is_object()) throw std::runtime_error("Invalid prefab component overrides");
        for(const auto& [local,components]:instance.component_overrides.items()) {
            if(!instance.mapping.contains(local) || !w.index.contains(instance.mapping.at(local)) || !components.is_object())
                throw std::runtime_error("Component overrides require a live prefab member");
            auto e=Handle(c,instance.mapping.at(local));
            for(const auto& [key,mask]:components.items()) {
                const auto& schema=Component(c,KeyId(key,3999));
                const bool present=e.has<ComponentData>(schema.entity);
                if(!mask.is_object() || mask.empty()) throw std::runtime_error("Invalid prefab component override");
                for(const auto& [name,_]:mask.items())
                    if(name!="present" && name!="enabled" && name!="properties") throw std::runtime_error("Unknown prefab component override field");
                if(mask.contains("present") && (!mask.at("present").is_boolean() || mask.at("present")!=present))
                    throw std::runtime_error("Prefab component presence override disagrees with entity");
                if(mask.contains("enabled") && (!mask.at("enabled").is_boolean() || mask.at("enabled")!=true || !present))
                    throw std::runtime_error("Invalid prefab component enabled override");
                if(mask.contains("properties")) {
                    const auto& fields=mask.at("properties");
                    if(!present || !fields.is_array() || fields.empty()) throw std::runtime_error("Invalid prefab component property overrides");
                    std::set<int> seen;
                    for(const auto& value:fields) {
                        const int fid=SchemaId(value,32);
                        if(!schema.fields.contains(fid) || !seen.insert(fid).second) throw std::runtime_error("Invalid prefab component property overrides");
                    }
                }
            }
        }
        w.instances.emplace(root,std::move(instance));
    }
}
std::shared_ptr<SceneWorld> CreateSceneWorld(const Json& scene,const Json& identity_checkpoint) {
    if(!scene.at("entities").is_array()) throw std::runtime_error("Scene entities must be an array");
    auto result=std::make_shared<SceneWorld>();
    result->features=scene.value("features",Json::object());
    if(!result->features.is_object()) throw std::runtime_error("Scene features must be an object");
    for(const auto& [name,value]:result->features.items()) {
        if(name!="2d" && name!="3d" && name!="gameplay" && name!="editor")
            throw std::runtime_error("Unknown scene feature section: "+name);
        if(!value.is_object()) throw std::runtime_error("Scene feature section must be an object: "+name);
    }
    ValidateFeatureMetadata(result->features);
    result->tilemaps=scene.value("tilemap_assets",Json::array());
    if(!result->tilemaps.is_array() || result->tilemaps.size()>256) throw std::runtime_error("At most 256 tilemap assets are allowed");
    for(const auto& tilemap:result->tilemaps) {
        if(!tilemap.is_object() || tilemap.value("version",0)!=1 || tilemap.value("type","")!="tilemap")
            throw std::runtime_error("Unsupported tilemap asset version/type");
        if(!tilemap.contains("id") || !tilemap.at("id").is_string() || !tilemap.contains("sprite") || !tilemap.at("sprite").is_string())
            throw std::runtime_error("Tilemap requires id and sprite");
        if(!tilemap.contains("width") || !tilemap.contains("height") || !tilemap.at("width").is_number_integer() || !tilemap.at("height").is_number_integer())
            throw std::runtime_error("Tilemap requires integer dimensions");
        const auto width=tilemap.at("width").get<std::int64_t>(), height=tilemap.at("height").get<std::int64_t>();
        if(width<1 || height<1 || width>4096 || height>4096 || !tilemap.contains("tiles") || !tilemap.at("tiles").is_array() ||
           tilemap.at("tiles").size()!=static_cast<std::size_t>(width*height)) throw std::runtime_error("Invalid tilemap dimensions or tiles");
    }
    result->materials=ReadMaterialAssets(scene.value("material_assets",Json::array()));
    for(const auto& prefab:scene.value("prefab_assets",Json::array()))
        MergeMaterialAssets(result->materials,prefab.value("material_assets",Json::array()));
    result->sprites=ReadSpriteAssets(scene.value("sprite_assets",Json::array()));
    for(const auto& prefab:scene.value("prefab_assets",Json::array()))
        MergeSpriteAssets(result->sprites,prefab.value("sprite_assets",Json::array()));
    result->sprite_state_assets=scene.value("sprite_state_assets",Json::array());
    if(!result->sprite_state_assets.is_array() || result->sprite_state_assets.size()>1024)
        throw std::runtime_error("At most 1024 sprite state machines are allowed");
    std::set<std::string> state_ids;
    for(const auto& asset:result->sprite_state_assets) {
        if(!asset.is_object() || asset.value("version",0)!=1 || asset.value("type","")!="sprite_state_machine" ||
           !asset.contains("id") || !asset.at("id").is_string() || !state_ids.insert(asset.at("id").get<std::string>()).second)
            throw std::runtime_error("Invalid sprite state machine asset");
        const auto sprite=asset.value("sprite",std::string{});
        if(!result->sprites.contains(sprite) || !asset.contains("states") || !asset.at("states").is_object() || asset.at("states").empty())
            throw std::runtime_error("Sprite state machine references an unknown sprite or has no states");
        const auto frame_count=result->sprites.at(sprite).at("columns").get<int>()*result->sprites.at(sprite).at("rows").get<int>();
        for(const auto& [state,frames]:asset.at("states").items()) {
            if(state.empty() || !frames.is_array() || frames.empty()) throw std::runtime_error("Sprite state requires nonempty frames");
            for(const auto& frame:frames) if(!frame.is_number_integer() || frame<0 || frame>=frame_count)
                throw std::runtime_error("Sprite state frame is outside its atlas");
        }
        const auto initial=asset.value("initial",std::string{});
        if(!asset.at("states").contains(initial) || !asset.contains("fps") || !asset.at("fps").is_number() ||
           !std::isfinite(asset.at("fps").get<double>()) || asset.at("fps")<=0 || asset.at("fps")>240 ||
           !asset.contains("loop") || !asset.at("loop").is_boolean())
            throw std::runtime_error("Invalid sprite state machine timing or initial state");
    }
    LoadComponentSchemas(*result,scene.value("component_definitions",Json::array()));
    LoadPrefabAssets(*result,scene);
    if(scene.contains("entity_serial")) {
        const auto& value=scene.at("entity_serial");
        if(!value.is_number_integer() || value<0 || value>std::numeric_limits<std::int64_t>::max())
            throw std::runtime_error("Invalid entity serial");
        result->serial=value.get<std::uint64_t>();
    }
    Ctx staging; staging.world=result;
    for(const auto& item:scene.at("entities")) {
        auto id=item.at("id").get<std::string>();
        result->used.insert(id); // Reserve original IDs even after deletion.
        if(id.starts_with("spawned_")) {
            const auto digits=id.substr(8);
            if(!digits.empty() && digits.size()<=19 && std::all_of(digits.begin(),digits.end(),[](char ch){return ch>='0' && ch<='9';})) {
                const auto serial=std::stoull(digits);
                if(serial<=static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) result->serial=std::max<std::uint64_t>(result->serial,serial);
            }
        }
        Tags tags;
        const auto tag_values=item.value("tags",Json::array());
        if(!tag_values.is_array()) throw std::runtime_error("Entity tags must be an array");
        for(const auto& value:tag_values) {
            auto tag=value.get<std::string>(); Text(tag,128,"entity tag");
            if(!tags.values.insert(tag).second) throw std::runtime_error("Duplicate entity tag");
        }
        if(tags.values.size()>256) throw std::runtime_error("At most 256 tags per entity are allowed");
        Mesh mesh{item.value("mesh",std::string{}),item.value("visible",true)};
        if(!mesh.asset.empty()) result->assets.insert(mesh.asset);
        const auto layer=item.value("layer",Json(0));
        if(!layer.is_number_integer() || layer<0 || layer>31) throw std::runtime_error("Entity layer must be an integer between 0 and 31");
        Insert(*result,id,item.value("name",id),
            {vec_from_json(item.at("position")),vec_from_json(item.at("rotation")),vec_from_json(item.at("scale"))},mesh,tags,
            {item.value("active",true),layer.get<std::int64_t>()},ReadCameraJson(item.value("camera",Json())),
            ReadMaterialBinding(item.value("material",Json()),result->materials),ReadSpriteBinding(item.value("sprite",Json()),result->sprites),ReadBodyConfig(item.value("rigid_body",Json())));
        auto sorting_layer=item.value("sorting_layer",std::string("default"));
        Text(sorting_layer,48,"sorting layer");
        const auto sorting_order=item.value("sorting_order",Json(0));
        if(!sorting_order.is_number_integer() || sorting_order<-1000000 || sorting_order>1000000)
            throw std::runtime_error("Invalid sorting order");
        result->render_order[id]={std::move(sorting_layer),sorting_order.get<std::int64_t>()};
        if(item.contains("sprite_state") && !item.at("sprite_state").is_null()) {
            const auto& binding=item.at("sprite_state");
            if(!binding.is_object() || !binding.contains("asset") || !binding.contains("state"))
                throw std::runtime_error("Invalid sprite state binding");
            const auto asset=binding.at("asset").get<std::string>(), state=binding.at("state").get<std::string>();
            auto found=std::find_if(result->sprite_state_assets.begin(),result->sprite_state_assets.end(),[&](const auto& value){return value.at("id")==asset;});
            if(found==result->sprite_state_assets.end() || !found->at("states").contains(state))
                throw std::runtime_error("Sprite state binding references an unknown asset or state");
            const auto entity_sprite=item.value("sprite",Json()).value("asset",std::string{});
            if(entity_sprite!=found->at("sprite").get<std::string>())
                throw std::runtime_error("Sprite state machine sprite differs from entity sprite");
            const auto& frames=found->at("states").at(state);
            const auto frame_count=result->sprites.at(entity_sprite).at("columns").get<int>()*result->sprites.at(entity_sprite).at("rows").get<int>();
            SpriteStateData current{asset,state,frames.at(0).get<std::int64_t>(),0,true};
            if(binding.contains("frame")) current.frame=binding.at("frame").get<std::int64_t>();
            if(binding.contains("elapsed")) current.elapsed=FromJson<double>(binding.at("elapsed"));
            if(binding.contains("playing")) current.playing=FromJson<bool>(binding.at("playing"));
            if(current.frame<0 || current.frame>=frame_count) throw std::runtime_error("Sprite state frame is invalid");
            result->sprite_states[id]=std::move(current);
        }
        const auto instances=item.value("components",Json::object());
        if(!instances.is_object()) throw std::runtime_error("Entity components must be an object");
        for(const auto& [key,instance]:instances.items()) {
            if(key.empty() || key.size()>4 || !std::all_of(key.begin(),key.end(),[](char c){return c>='0' && c<='9';}))
                throw std::runtime_error("Invalid component ID key");
            const int cid=std::stoi(key);
            if(std::to_string(cid)!=key) throw std::runtime_error("Invalid component ID key");
            AddComponent(staging,{id},cid);
            SetComponentEnabled(staging,{id},cid,instance.value("enabled",true));
            const auto fields=instance.value("properties",Json::object());
            if(!fields.is_object()) throw std::runtime_error("Component properties must be an object");
            for(const auto& [field,value]:fields.items()) {
                if(field.empty() || field.size()>2 || !std::all_of(field.begin(),field.end(),[](char c){return c>='0' && c<='9';}))
                    throw std::runtime_error("Invalid property ID key");
                const int fid=std::stoi(field);
                if(std::to_string(fid)!=field) throw std::runtime_error("Invalid property ID key");
                auto& schema=Component(staging,cid);
                if(!schema.fields.contains(fid)) throw std::runtime_error("Unknown component property");
                WriteComponentProperty(staging,{id},cid,fid,ValueFromJson(schema.fields.at(fid).type,value));
            }
        }
    }
    for(const auto& item:scene.at("entities")) {
        const auto parent=item.value("parent",std::string{});
        if(!parent.empty()) SetParent(staging,{item.at("id").get<std::string>()},{parent});
    }
    LoadPrefabInstances(staging,scene);
    SetActiveCamera(staging,{scene.value("active_camera",std::string{})});
    if(!identity_checkpoint.is_null()) {
        const auto& saved=identity_checkpoint;
        if(!saved.is_object() || saved.size()!=3 || !saved.contains("version") ||
           !saved.at("version").is_number_integer() || saved.at("version")!=1)
            throw std::runtime_error("Invalid scene identity checkpoint/version");
        auto restore=[&](const char* key,const std::set<std::string>& required,std::size_t text_limit) {
            const auto& values=saved.at(key);
            if(!values.is_array()) throw std::runtime_error("Scene identity checkpoint requires arrays");
            std::set<std::string> restored;
            for(const auto& value:values) {
                if(!value.is_string()) throw std::runtime_error("Scene identity checkpoint requires text");
                const auto text=value.get<std::string>(); Text(text,text_limit,key);
                if(!restored.insert(text).second) throw std::runtime_error("Duplicate scene identity checkpoint entry");
            }
            if(!std::includes(restored.begin(),restored.end(),required.begin(),required.end()))
                throw std::runtime_error("Scene identity checkpoint omits live or prefab state");
            return restored;
        };
        result->used=restore("reserved_ids",result->used,128);
        result->assets=restore("meshes",result->assets,4096);
    }
    return result;
}
Json SceneIdentityCheckpoint(const Ctx& c) {
    const auto& w=World(c);
    auto reserved=w.used;
    for(const auto& [id,_]:w.index) reserved.insert(id);
    return {{"version",1},{"reserved_ids",reserved},{"meshes",w.assets}};
}
Entity& Find(Ctx& c,const std::string& id) { return Handle(c,id).ensure<Entity>(); }
bool EntityExists(const Ctx& c,EntityRef id) { return c.world && c.world->index.contains(id.id); }
Vec3 GetPosition(Ctx& c,EntityRef id) { return Handle(c,id.id).get<Entity>().position; }
Vec3 GetRotation(Ctx& c,EntityRef id) { return Handle(c,id.id).get<Entity>().rotation; }
Vec3 GetScale(Ctx& c,EntityRef id) { return Handle(c,id.id).get<Entity>().scale; }
void SetPosition(Ctx& c,EntityRef id,Vec3 value) { value=finite(value); auto e=Handle(c,id.id); e.ensure<Entity>().position=value; e.modified<Entity>(); }
void SetRotation(Ctx& c,EntityRef id,Vec3 value) { value=finite(value); auto e=Handle(c,id.id); e.ensure<Entity>().rotation=value; e.modified<Entity>(); }
void SetScale(Ctx& c,EntityRef id,Vec3 value) { value=finite(value); auto e=Handle(c,id.id); e.ensure<Entity>().scale=value; e.modified<Entity>(); }
void Translate(Ctx& c,EntityRef id,Vec3 value) { SetPosition(c,id,GetPosition(c,id)+value); }
void Rotate(Ctx& c,EntityRef id,Vec3 value) { SetRotation(c,id,GetRotation(c,id)+value); }
static std::string NextId(SceneWorld& w) {
    std::string id;
    do {
        if(w.serial>=static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) throw std::runtime_error("Entity ID sequence exhausted");
        id="spawned_"+std::to_string(++w.serial);
    } while(w.used.contains(id));
    return id;
}
static EntityRef InstantiatePrefabImpl(Ctx& c,std::string asset,EntityRef parent,Vec3 position) {
    auto& w=World(c); position=finite(position);
    if(!w.prefabs.contains(asset)) throw std::runtime_error("Unknown prefab asset: "+asset);
    const auto& prefab=w.prefabs.at(asset);
    if(w.index.size()+prefab.nodes.size()>65536) throw std::runtime_error("At most 65536 entities are allowed");
    int ancestors=0;
    for(auto p=parent; !p.id.empty(); p=GetParent(c,p)) ++ancestors;
    if(ancestors+prefab.depth>256) throw std::runtime_error("Entity hierarchy exceeds 256 levels");
    PrefabInstance instance{asset,{}, {}};
    std::uint64_t serial=w.serial;
    auto reserve=[&](const std::string& local) {
        std::string id;
        do {
            if(serial>=static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) throw std::runtime_error("Entity ID sequence exhausted");
            id="spawned_"+std::to_string(++serial);
        } while(w.used.contains(id));
        instance.mapping.emplace(local,id);
    };
    // Reserve a complete mapping before mutating the live world or serial.
    reserve(prefab.root);
    for(const auto& [local,_]:prefab.nodes) if(local!=prefab.root) reserve(local);
    const auto root=instance.mapping.at(prefab.root);
    for(const auto& [local,id]:instance.mapping) {
        auto e=w.world.entity().is_a(w.world.entity(prefab.nodes.at(local)))
            .set<Identity>({id,prefab.names.at(local)}).set<PrefabLink>({asset,local,root});
        for(const auto& [_,schema]:w.components) if(e.has<ComponentData>(schema.entity)) {
            auto data=e.get<ComponentData>(schema.entity); RemapPrefabData(data,instance.mapping);
            e.set<ComponentData>(schema.entity,data);
        }
        w.index.emplace(id,e.id()); w.used.insert(id);
    }
    for(const auto& [local,id]:instance.mapping) {
        const auto target=local==prefab.root ? parent.id : instance.mapping.at(prefab.parents.at(local));
        if(!target.empty()) Handle(c,id).child_of(Handle(c,target));
    }
    w.serial=serial;
    w.instances.emplace(root,std::move(instance));
    SetPosition(c,{root},position); // Explicit placement is an instance override.
    RefreshEntityActivity(c);
    return {root};
}
bool IsPrefabInstance(Ctx& c,EntityRef id) { return EntityExists(c,id) && Handle(c,id.id).has<PrefabLink>(); }
std::string GetPrefabAsset(Ctx& c,EntityRef id) {
    return IsPrefabInstance(c,id) ? Handle(c,id.id).get<PrefabLink>().asset : std::string{};
}
EntityRef GetPrefabRoot(Ctx& c,EntityRef id) {
    return IsPrefabInstance(c,id) ? EntityRef{Handle(c,id.id).get<PrefabLink>().root} : EntityRef{};
}
EntityRef GetPrefabEntity(Ctx& c,EntityRef id,std::string local) {
    if(!IsPrefabInstance(c,id)) return {};
    const auto& link=Handle(c,id.id).get<PrefabLink>();
    const auto& mapping=World(c).instances.at(link.root).mapping;
    auto found=mapping.find(local);
    return found!=mapping.end() && EntityExists(c,{found->second}) ? EntityRef{found->second} : EntityRef{};
}
static void ResetPrefabInstanceImpl(Ctx& c,EntityRef id,bool keep_placement) {
    if(!IsPrefabInstance(c,id)) throw std::runtime_error("Reset requires a live prefab instance member");
    auto& w=World(c);
    const auto root=GetPrefabRoot(c,id).id;
    const auto& instance=w.instances.at(root);
    const auto& prefab=w.prefabs.at(instance.asset);
    const auto placement=Handle(c,root).get<Entity>();
    const bool placement_owned=Handle(c,root).owns<Entity>();
    const auto root_parent=GetParent(c,{root}).id;
    std::set<std::string> members, removed;
    for(const auto& [_,sid]:instance.mapping) members.insert(sid);

    // Plan the final hierarchy before touching entities, timers or observers.
    // Added instance roots own even their detached members; target members are
    // protected when they have been reparented underneath an added descendant.
    std::map<std::string,std::vector<std::string>> children;
    std::map<std::string,std::string> parents;
    for(const auto& [sid,_]:w.index) {
        parents[sid]=GetParent(c,{sid}).id;
        children[parents.at(sid)].push_back(sid);
    }
    std::vector<std::string> pending;
    for(const auto& sid:members) for(const auto& child:children[sid]) pending.push_back(child);
    for(std::size_t i=0;i<pending.size();++i) {
        const auto sid=pending[i];
        if(members.contains(sid) || !w.index.contains(sid) || !removed.insert(sid).second) continue;
        for(const auto& child:children[sid]) pending.push_back(child);
        if(w.instances.contains(sid))
            for(const auto& [_,member]:w.instances.at(sid).mapping) pending.push_back(member);
    }
    for(const auto& sid:removed) parents.erase(sid);
    for(const auto& [local,sid]:instance.mapping)
        parents[sid]=local==prefab.root ? root_parent : instance.mapping.at(prefab.parents.at(local));
    if(parents.size()>65536) throw std::runtime_error("At most 65536 entities are allowed");
    for(const auto& [sid,_]:parents) {
        std::set<std::string> visited;
        for(auto current=sid; !current.empty(); current=parents.at(current)) {
            if(!parents.contains(current)) throw std::runtime_error("Reset would remove the instance root's parent");
            if(!visited.insert(current).second) throw std::runtime_error("Reset would create an entity hierarchy cycle");
            if(visited.size()>256) throw std::runtime_error("Entity hierarchy exceeds 256 levels");
        }
    }
    std::map<std::string,std::map<ecs_entity_t,ComponentData>> components;
    for(const auto& [local,_]:instance.mapping) {
        auto base=w.world.entity(prefab.nodes.at(local));
        for(const auto& [_,schema]:w.components) if(base.has<ComponentData>(schema.entity)) {
            auto data=base.get<ComponentData>(schema.entity);
            RemapPrefabData(data,instance.mapping);
            components[local].emplace(schema.entity,std::move(data));
        }
    }

    // Detach protected entities first: Flecs ChildOf deletion must not cascade
    // into a member whose current parent is about to disappear.
    for(const auto& sid:members) if(w.index.contains(sid)) Handle(c,sid).remove(flecs::ChildOf,flecs::Wildcard);
    for(const auto& sid:removed) Handle(c,sid).remove(flecs::ChildOf,flecs::Wildcard);
    for(const auto& sid:removed) {
        ForgetEntityEvents(c,sid);
        c.entity_variables.erase(sid);
        ForgetEntityFlow(c,sid);
        ForgetEntityContinuations(c,sid);
        auto handle=w.index.at(sid);
        w.index.erase(sid); w.instances.erase(sid);
        w.world.entity(handle).destruct();
    }
    std::vector<std::string> restored;
    for(const auto& [local,sid]:instance.mapping) {
        auto base=w.world.entity(prefab.nodes.at(local));
        if(!w.index.contains(sid)) {
            auto e=w.world.entity().is_a(base).set<PrefabLink>({instance.asset,local,root});
            w.index.emplace(sid,e.id()); restored.push_back(sid);
        }
        auto e=Handle(c,sid);
        e.set<Identity>({sid,prefab.names.at(local)});
        e.remove<Entity>().remove<Mesh>().remove<Tags>().remove<Activity>().remove<Camera>().remove<MaterialBinding>().remove<SpriteBinding>().remove<RigidBodyConfig>();
        if(sid==root && keep_placement && (placement_owned || placement!=base.get<Entity>())) e.set<Entity>(placement);
        for(const auto& [_,schema]:w.components) {
            auto found=components[local].find(schema.entity);
            if(found==components[local].end()) e.remove<ComponentData>(schema.entity);
            else e.set<ComponentData>(schema.entity,found->second);
        }
    }
    for(const auto& sid:members) if(!parents.at(sid).empty()) Handle(c,sid).child_of(Handle(c,parents.at(sid)));
    w.instances.at(root).component_overrides=Json::object();
    w.active_camera=GetActiveCamera(c).id;
    for(const auto& sid:restored) RestoreEntityEvents(c,sid);
    RefreshEntityActivity(c);
}
static void ApplyPrefabOverridesImpl(Ctx& c,EntityRef id,bool keep_placement) {
    if(!IsPrefabInstance(c,id)) throw std::runtime_error("Apply requires a live prefab instance member");
    auto& w=World(c);
    const auto candidate=PlanPrefabApply(Snapshot(c).at("scene"),GetPrefabRoot(c,id).id,keep_placement,w.used,w.serial);
    // Validate the full scene, dependencies, component values and inheritance in
    // a separate world before touching live handles or delivery generations.
    const auto staging=CreateSceneWorld(candidate);
    auto& next=*staging;
    auto previous_templates=std::move(w.prefabs);
    w.prefabs.clear();
    LoadPrefabAssets(w,candidate);

    // Preserve every surviving handle; detach first to prevent ChildOf deletion
    // from erasing ordinary children that the transaction has reparented.
    for(const auto& [_,handle]:w.index) w.world.entity(handle).remove(flecs::ChildOf,flecs::Wildcard);
    for(auto it=w.index.begin();it!=w.index.end();) {
        if(!next.index.contains(it->first)) {
            c.entity_variables.erase(it->first);
            ForgetEntityEvents(c,it->first);
            ForgetEntityFlow(c,it->first);
            ForgetEntityContinuations(c,it->first);
            w.world.entity(it->second).destruct(); it=w.index.erase(it);
        } else ++it;
    }
    std::vector<std::string> created;
    for(const auto& [sid,handle]:next.index) {
        auto source=next.world.entity(handle);
        if(!w.index.contains(sid)) { w.index.emplace(sid,w.world.entity().id()); created.push_back(sid); }
        auto e=Handle(c,sid);
        e.remove(flecs::IsA,flecs::Wildcard).remove<PrefabLink>();
        e.set<Identity>(source.get<Identity>()).set<Entity>(source.get<Entity>())
            .set<Mesh>(source.get<Mesh>()).set<Tags>(source.get<Tags>()).set<Activity>(source.get<Activity>()).set<Camera>(source.get<Camera>()).set<MaterialBinding>(source.get<MaterialBinding>()).set<SpriteBinding>(source.get<SpriteBinding>());
        e.set<RigidBodyConfig>(source.get<RigidBodyConfig>());
        if(source.has<PrefabLink>()) {
            const auto& link=source.get<PrefabLink>();
            auto base=w.world.entity(w.prefabs.at(link.asset).nodes.at(link.local));
            e.is_a(base).set<PrefabLink>(link);
            if(!source.owns<Entity>()) e.remove<Entity>();
            if(!source.owns<Mesh>()) e.remove<Mesh>();
            if(!source.owns<Tags>()) e.remove<Tags>();
            if(!source.owns<Activity>()) e.remove<Activity>();
            if(!source.owns<Camera>()) e.remove<Camera>();
            if(!source.owns<MaterialBinding>()) e.remove<MaterialBinding>();
            if(!source.owns<SpriteBinding>()) e.remove<SpriteBinding>();
            if(!source.owns<RigidBodyConfig>()) e.remove<RigidBodyConfig>();
        }
        for(const auto& [cid,schema]:w.components) {
            const auto target_schema=next.components.at(cid).entity;
            if(source.has<ComponentData>(target_schema)) e.set<ComponentData>(schema.entity,source.get<ComponentData>(target_schema));
            else e.remove<ComponentData>(schema.entity);
        }
    }
    for(const auto& [sid,handle]:next.index) {
        auto parent=next.world.entity(handle).target(flecs::ChildOf);
        if(parent.id()) Handle(c,sid).child_of(Handle(c,parent.get<Identity>().id));
    }
    w.instances=std::move(next.instances);
    w.active_camera=next.active_camera;
    w.used.insert(next.used.begin(),next.used.end()); w.serial=next.serial;
    for(const auto& [_,prefab]:previous_templates) for(const auto& [__,handle]:prefab.nodes)
        if(w.world.entity(handle).is_alive()) w.world.entity(handle).destruct();
    for(const auto& sid:created) RestoreEntityEvents(c,sid);
    RefreshEntityActivity(c);
    PruneAnimations(c);
}
template<class Operation> static EntityRef PrefabPhysicsTransaction(Ctx& c,Operation operation,const std::set<std::string>& reset={}) {
    bool needed=bool(c.physics);
    for(const auto& [_,asset]:World(c).prefabs) for(const auto& [__,handle]:asset.nodes)
        needed=needed||!World(c).world.entity(handle).get<RigidBodyConfig>().value.is_null();
    if(!needed && !HasEntityDestroyedListeners(c)) return operation(c);
    // Validate the final scene and native bodies before changing live handles,
    // subscriptions or timers. The source may be inside a contact callback.
    auto prepare=[&] {
        Ctx next;
        LoadScene(next,Snapshot(c).at("scene"),SceneIdentityCheckpoint(c));
        next.physics_scene=c.physics_scene;
        if(c.physics) { next.physics=std::make_shared<PhysicsWorld>(); next.physics->restore(c.physics->checkpoint()); }
        const auto result=operation(next);
        std::set<std::string> replace=reset;
        for(const auto& [id,handle]:World(next).index)
            if(!EntityExists(c,{id}) || Handle(c,id).get<RigidBodyConfig>()!=World(next).world.entity(handle).get<RigidBodyConfig>())
                replace.insert(id);
        for(auto it=next.physics_scene.bodies.begin();it!=next.physics_scene.bodies.end();) {
            if(replace.contains(it->first)||!EntityExists(next,{it->first})) {
                next.physics->remove(it->first); it=next.physics_scene.bodies.erase(it);
            } else ++it;
        }
        SyncPhysics(next);
        for(const auto& id:replace) if(EntityExists(next,{id})) {
            const auto& config=Handle(next,id).get<RigidBodyConfig>().value;
            if(!config.is_null()) CreateAuthoredBody(next,{id},config);
        }
        return std::make_pair(std::move(next),result);
    };
    auto candidate=prepare();
    auto removed=[&] {
        std::set<std::string> ids;
        for(const auto& [id,_]:World(c).index) if(!EntityExists(candidate.first,{id})) ids.insert(id);
        return ids;
    };
    auto commit=[&] {
        operation(c);
        c.physics=std::move(candidate.first.physics); c.physics_scene=std::move(candidate.first.physics_scene);
    };
    if(!HasEntityDestroyedListeners(c) || removed().empty()) { commit(); return candidate.second; }
    {
        DestructionEdit edit(c);
        for(int pass=0;;++pass) {
            if(pass>=256) throw std::runtime_error("Destruction callbacks did not settle within 256 scene-edit passes");
            const auto targets=removed(); auto& notified=World(c).destroying;
            for(const auto& id:notified) if(!targets.contains(id)) throw std::runtime_error("Cannot cancel a pending entity destruction");
            std::vector<std::string> fresh;
            for(const auto& id:targets) if(notified.insert(id).second) fresh.push_back(id);
            if(fresh.empty()) break;
            for(const auto& id:fresh) NotifyEntityDestroyed(c,{id});
            // Include callback-created entities, property writes and physics changes.
            candidate=prepare();
        }
        commit();
    }
    FlushSceneEdits(c);
    return candidate.second;
}
EntityRef InstantiatePrefab(Ctx& c,std::string asset,EntityRef parent,Vec3 position) {
    return PrefabPhysicsTransaction(c,[&](Ctx& target){return InstantiatePrefabImpl(target,asset,parent,position);});
}
void ResetPrefabInstance(Ctx& c,EntityRef id,bool keep_placement) {
    if(!IsPrefabInstance(c,id)) throw std::runtime_error("Reset requires a live prefab instance member");
    if(DeferSceneEdit(c,1,id,keep_placement)) return;
    std::set<std::string> reset;
    for(const auto& [_,member]:World(c).instances.at(GetPrefabRoot(c,id).id).mapping) reset.insert(member);
    PrefabPhysicsTransaction(c,[&](Ctx& target){ResetPrefabInstanceImpl(target,id,keep_placement); return EntityRef{};},reset);
}
void ApplyPrefabOverrides(Ctx& c,EntityRef id,bool keep_placement) {
    if(!IsPrefabInstance(c,id)) throw std::runtime_error("Apply requires a live prefab instance member");
    if(DeferSceneEdit(c,2,id,keep_placement)) return;
    PrefabPhysicsTransaction(c,[&](Ctx& target){ApplyPrefabOverridesImpl(target,id,keep_placement); return EntityRef{};});
}
EntityRef SpawnEntity(Ctx& c,std::string name,std::string mesh,Vec3 position) {
    auto& w=World(c); Text(name,512,"entity name"); position=finite(position);
    if(!mesh.empty() && !w.assets.contains(mesh)) throw std::runtime_error("Mesh is not preloaded in this scene: "+mesh);
    const auto id=NextId(w);
    Insert(w,id,name,{position,Vec3{0},Vec3{1}},{mesh,true},{});
    RefreshEntityActivity(c);
    return {id};
}
EntityRef CloneEntity(Ctx& c,EntityRef source,std::string name) {
    auto e=Handle(c,source.id);
    CheckPhysicsClone(c,source);
    if(name.empty()) name=e.get<Identity>().name;
    Text(name,512,"entity name");
    const auto transform=e.get<Entity>(); const auto mesh=e.get<Mesh>(); const auto tags=e.get<Tags>(); const auto activity=e.get<Activity>();
    const auto parent=GetParent(c,source);
    std::vector<std::pair<ecs_entity_t,ComponentData>> components;
    for(const auto& [_,schema]:World(c).components)
        if(e.has<ComponentData>(schema.entity)) components.emplace_back(schema.entity,e.get<ComponentData>(schema.entity));
    const auto id=NextId(World(c));
    Insert(World(c),id,name,transform,mesh,tags,activity,e.get<Camera>(),e.get<MaterialBinding>(),e.get<SpriteBinding>(),e.get<RigidBodyConfig>());
    if(const auto order=World(c).render_order.find(source.id); order!=World(c).render_order.end()) World(c).render_order[id]=order->second;
    if(const auto state=World(c).sprite_states.find(source.id); state!=World(c).sprite_states.end()) World(c).sprite_states[id]=state->second;
    for(const auto& [handle,data]:components) Handle(c,id).set<ComponentData>(handle,data);
    if(!parent.id.empty()) Handle(c,id).child_of(Handle(c,parent.id));
    ClonePhysics(c,source,{id});
    CloneAnimation(c,source,{id});
    if(const auto values=c.entity_variables.find(source.id);values!=c.entity_variables.end()) c.entity_variables[id]=values->second;
    RefreshEntityActivity(c);
    return {id};
}
EntityRef GetEntityById(Ctx& c,std::string id) { return EntityExists(c,{id}) ? EntityRef{id} : EntityRef{}; }
Array<EntityRef> GetAllEntities(Ctx& c) {
    Array<EntityRef> result;
    for(const auto& [id,_]:World(c).index) result.push_back({id});
    return result;
}
std::int64_t EntityCount(const Ctx& c) { return static_cast<std::int64_t>(World(c).index.size()); }
std::uint64_t EntitySerial(const Ctx& c) { return World(c).serial; }
std::string GetEntityName(Ctx& c,EntityRef id) { return Handle(c,id.id).get<Identity>().name; }
std::string GetEntityMesh(const Ctx& c,EntityRef id) { return Handle(c,id.id).get<Mesh>().asset; }
void SetEntityName(Ctx& c,EntityRef id,std::string name) {
    Text(name,512,"entity name"); auto e=Handle(c,id.id); e.get_mut<Identity>().name=std::move(name); e.modified<Identity>();
}
Array<EntityRef> FindEntitiesByName(Ctx& c,std::string name) {
    Array<EntityRef> result;
    for(const auto& [id,handle]:World(c).index) if(World(c).world.entity(handle).get<Identity>().name==name) result.push_back({id});
    return result;
}
EntityRef GetParent(Ctx& c,EntityRef child) {
    auto parent=Handle(c,child.id).target(flecs::ChildOf);
    return parent.id() ? EntityRef{parent.get<Identity>().id} : EntityRef{};
}
Array<EntityRef> GetChildren(Ctx& c,EntityRef parent) {
    Array<EntityRef> result;
    if(parent.id.empty()) {
        for(const auto& [id,_]:World(c).index) if(GetParent(c,{id})==parent) result.push_back({id});
    } else {
        Handle(c,parent.id).children([&](flecs::entity child) {
            if(child.has<Identity>()) result.push_back({child.get<Identity>().id});
        });
        std::sort(result.begin(),result.end(),[](const auto& a,const auto& b){return a.id<b.id;});
    }
    return result;
}
void SetParent(Ctx& c,EntityRef child,EntityRef parent) {
    auto e=Handle(c,child.id);
    if(parent==GetParent(c,child)) return;
    if(World(c).destroying.contains(child.id)) throw std::runtime_error("Cannot reparent an entity pending destruction");
    int depth=1;
    for(auto p=parent; !p.id.empty(); p=GetParent(c,p)) {
        if(p==child) throw std::runtime_error("Entity hierarchy cycle");
        if(++depth>256) throw std::runtime_error("Entity hierarchy exceeds 256 levels");
    }
    // Validate the entire affected subtree before changing the relationship.
    std::vector<std::pair<EntityRef,int>> pending{{child,depth}};
    for(std::size_t i=0;i<pending.size();++i) {
        const auto [id,level]=pending[i];
        if(level>256) throw std::runtime_error("Entity hierarchy exceeds 256 levels");
        for(auto descendant:GetChildren(c,id)) pending.emplace_back(descendant,level+1);
    }
    if(parent.id.empty()) e.remove(flecs::ChildOf,flecs::Wildcard);
    else e.child_of(Handle(c,parent.id));
    RefreshEntityActivity(c);
}
static std::set<std::string> DestructionTargets(Ctx& c,EntityRef id) {
    auto& w=World(c);
    std::set<std::string> removed;
    std::vector<EntityRef> pending{id};
    for(std::size_t i=0;i<pending.size();++i) {
        const auto child=pending[i];
        if(!EntityExists(c,child) || !removed.insert(child.id).second) continue;
        for(auto descendant:GetChildren(c,child)) pending.push_back(descendant);
        // An instance owns its mapped members, including reparented members.
        if(w.instances.contains(child.id))
            for(const auto& [_,member]:w.instances.at(child.id).mapping) pending.push_back({member});
    }
    return removed;
}
static void DestroyEntities(Ctx& c,const std::set<std::string>& removed) {
    auto& w=World(c);
    std::vector<ecs_entity_t> handles;
    for(const auto& child:removed) {
        c.entity_variables.erase(child);
        ForgetEntityEvents(c,child); handles.push_back(w.index.at(child));
        ForgetEntityFlow(c,child);
        ForgetEntityContinuations(c,child);
        c.animation.players.erase(child);
        w.index.erase(child); w.instances.erase(child); w.render_order.erase(child); w.sprite_states.erase(child);
    }
    // ChildOf performs recursive cleanup. Extra handles cover detached members.
    for(auto handle:handles) if(w.world.entity(handle).is_alive()) w.world.entity(handle).destruct();
    w.active_camera=GetActiveCamera(c).id;
    RefreshEntityActivity(c);
}
void DestroyEntity(Ctx& c,EntityRef id) {
    if(!EntityExists(c,id)) return; // Safe to destroy twice; empty reference is a no-op.
    if(DeferSceneEdit(c,0,id)) return;
    if(!HasEntityDestroyedListeners(c)) { DestroyEntities(c,DestructionTargets(c,id)); return; }
    {
        DestructionEdit edit(c);
        for(int pass=0;;++pass) {
            if(pass>=256) throw std::runtime_error("Destruction callbacks did not settle within 256 scene-edit passes");
            const auto targets=DestructionTargets(c,id); auto& notified=World(c).destroying;
            std::vector<std::string> fresh;
            for(const auto& target:targets) if(notified.insert(target).second) fresh.push_back(target);
            if(fresh.empty()) break;
            for(const auto& target:fresh) NotifyEntityDestroyed(c,{target});
        }
        DestroyEntities(c,World(c).destroying);
    }
    FlushSceneEdits(c);
}
static glm::dmat4 Matrix(const Ctx& c,const std::string& id) {
    std::vector<Entity> chain;
    auto e=Handle(c,id);
    while(e.id()) { chain.push_back(e.get<Entity>()); e=e.target(flecs::ChildOf); }
    glm::dmat4 matrix(1.);
    for(auto it=chain.rbegin();it!=chain.rend();++it) {
        matrix=glm::translate(matrix,it->position);
        matrix=glm::rotate(matrix,glm::radians(it->rotation.y),Vec3{0,1,0});
        matrix=glm::rotate(matrix,glm::radians(it->rotation.x),Vec3{1,0,0});
        matrix=glm::rotate(matrix,glm::radians(it->rotation.z),Vec3{0,0,1});
        matrix=glm::scale(matrix,it->scale);
    }
    for(int col=0;col<4;++col) for(int row=0;row<4;++row) finite(matrix[col][row]);
    return matrix;
}
Vec3 GetWorldPosition(Ctx& c,EntityRef id) { return finite(Vec3{Matrix(c,id.id)[3]}); }
glm::dmat4 GetWorldMatrix(const Ctx& c,EntityRef id) { return Matrix(c,id.id); }
void SetPhysicsWorldPose(Ctx& c,EntityRef id,Vec3 position,glm::dquat rotation) {
    auto parent=GetParent(c,id);
    auto pose=glm::mat4_cast(rotation); pose[3]=glm::dvec4(position,1);
    if(!parent.id.empty()) pose=glm::inverse(Matrix(c,parent.id))*pose;
    for(int col=0;col<3;++col) pose[col]/=glm::length(Vec3(pose[col]));
    double yaw,pitch,roll; glm::extractEulerAngleYXZ(pose,yaw,pitch,roll);
    auto e=Handle(c,id.id); auto value=e.get<Entity>();
    value.position=finite(Vec3(pose[3])); value.rotation=finite(glm::degrees(Vec3(pitch,yaw,roll)));
    if(value!=e.get<Entity>()) { e.set<Entity>(value); }
}
bool HasCamera(const Ctx& c,EntityRef id) { return EntityExists(c,id) && Handle(c,id.id).get<Camera>().present; }
static Camera ReadCamera(const Ctx& c,EntityRef id) {
    if(!HasCamera(c,id)) throw std::runtime_error("Entity is not a camera: "+id.id);
    return Handle(c,id.id).get<Camera>();
}
static void WriteCamera(Ctx& c,EntityRef id,const Camera& camera) {
    CheckCamera(camera); Handle(c,id.id).set<Camera>(camera);
}
EntityRef CreateCamera(Ctx& c,std::string name,Vec3 position) {
    auto id=SpawnEntity(c,name,"",position);
    Camera camera; camera.present=true; WriteCamera(c,id,camera);
    return id;
}
EntityRef GetActiveCamera(const Ctx& c) {
    const auto& id=World(c).active_camera;
    return HasCamera(c,{id}) ? EntityRef{id} : EntityRef{};
}
void SetActiveCamera(Ctx& c,EntityRef id) {
    if(!id.id.empty()) ReadCamera(c,id);
    World(c).active_camera=id.id;
}
void SetCameraPerspective(Ctx& c,EntityRef id,double fov,double near_clip,double far_clip) {
    auto camera=ReadCamera(c,id); camera.orthographic=false; camera.fov=fov;
    camera.near_clip=near_clip; camera.far_clip=far_clip; WriteCamera(c,id,camera);
}
void SetCameraOrthographic(Ctx& c,EntityRef id,double size,double near_clip,double far_clip) {
    auto camera=ReadCamera(c,id); camera.orthographic=true; camera.size=size;
    camera.near_clip=near_clip; camera.far_clip=far_clip; WriteCamera(c,id,camera);
}
double GetCameraFOV(Ctx& c,EntityRef id) { return ReadCamera(c,id).fov; }
void SetCameraFOV(Ctx& c,EntityRef id,double value) { auto camera=ReadCamera(c,id); camera.fov=value; WriteCamera(c,id,camera); }
double GetCameraSize(Ctx& c,EntityRef id) { return ReadCamera(c,id).size; }
void SetCameraSize(Ctx& c,EntityRef id,double value) { auto camera=ReadCamera(c,id); camera.size=value; WriteCamera(c,id,camera); }
void SetCameraClip(Ctx& c,EntityRef id,double near_clip,double far_clip) {
    auto camera=ReadCamera(c,id); camera.near_clip=near_clip; camera.far_clip=far_clip; WriteCamera(c,id,camera);
}
static glm::dmat4 RotationMatrix(const Ctx& c,const std::string& id) {
    std::vector<Vec3> chain;
    for(auto e=Handle(c,id); e.id(); e=e.target(flecs::ChildOf)) chain.push_back(e.get<Entity>().rotation);
    glm::dmat4 rotation(1.);
    for(auto it=chain.rbegin(); it!=chain.rend(); ++it)
        rotation*=glm::eulerAngleYXZ(glm::radians(it->y),glm::radians(it->x),glm::radians(it->z));
    return rotation;
}
void CameraLookAt(Ctx& c,EntityRef id,Vec3 target,Vec3 up) {
    ReadCamera(c,id); target=finite(target); up=finite(up);
    const auto position=GetWorldPosition(c,id);
    auto direction=finite(target-position);
    if(glm::length(direction)<1e-9 || glm::length(up)<1e-9) throw std::runtime_error("Camera Look At needs distinct positions and a nonzero up vector");
    direction=Normalize(direction); up=Normalize(up);
    if(glm::length(glm::cross(direction,up))<1e-9) throw std::runtime_error("Camera up vector is parallel to its view direction");
    auto desired=glm::inverse(glm::lookAtRH(position,target,up));
    const auto parent=GetParent(c,id);
    if(!parent.id.empty()) desired=glm::transpose(RotationMatrix(c,parent.id))*desired;
    double yaw,pitch,roll;
    glm::extractEulerAngleYXZ(desired,yaw,pitch,roll);
    SetRotation(c,id,finite(glm::degrees(Vec3{pitch,yaw,roll})));
}
void CameraFollow(Ctx& c,EntityRef id,EntityRef target,Vec3 offset,double rate) {
    ReadCamera(c,id); offset=finite(offset); rate=finite(rate);
    if(rate<0 || !std::isfinite(c.dt) || c.dt<0) throw std::runtime_error("Camera follow rate and delta time must be nonnegative");
    const auto desired=finite(GetWorldPosition(c,target)+offset);
    const auto current=GetWorldPosition(c,id);
    const double amount=rate==0 ? 1. : -std::expm1(-rate*c.dt);
    Vec3 position=finite(current+(desired-current)*amount);
    const auto parent=GetParent(c,id);
    if(!parent.id.empty()) {
        const auto matrix=Matrix(c,parent.id);
        const double determinant=glm::determinant(matrix);
        if(!std::isfinite(determinant) || std::abs(determinant)<1e-12) throw std::runtime_error("Camera follow parent transform is not invertible");
        position=finite(Vec3{glm::inverse(matrix)*glm::dvec4(position,1.)});
    }
    SetPosition(c,id,position);
}
static std::optional<std::pair<glm::dmat4,glm::dmat4>> CameraMatrices(const Ctx& c,EntityRef id,double aspect) {
    if(!std::isfinite(aspect) || aspect<=0) throw std::runtime_error("Camera aspect must be positive");
    if(id.id.empty() || !HasCamera(c,id) || !IsEntityActive(c,id)) return std::nullopt;
    const auto camera=ReadCamera(c,id);
    // Lens orientation inherits rotations only; entity scale affects position, not FOV.
    auto pose=RotationMatrix(c,id.id); pose[3]=glm::dvec4(Vec3{Matrix(c,id.id)[3]},1.);
    const auto view=glm::inverse(pose);
    const auto projection=camera.orthographic ?
        glm::orthoRH_ZO(-camera.size*aspect*.5,camera.size*aspect*.5,-camera.size*.5,camera.size*.5,camera.near_clip,camera.far_clip) :
        glm::perspectiveRH_ZO(glm::radians(camera.fov),aspect,camera.near_clip,camera.far_clip);
    for(const auto* matrix:{&view,&projection}) for(int col=0;col<4;++col) for(int row=0;row<4;++row)
        if(!std::isfinite((*matrix)[col][row])) throw std::runtime_error("Camera matrix contains a non-finite value");
    return std::make_pair(view,projection);
}
std::optional<std::pair<glm::mat4,glm::mat4>> GameCameraMatrices(const Ctx& c,double aspect) {
    const auto matrices=CameraMatrices(c,GetActiveCamera(c),aspect);
    if(!matrices) return std::nullopt;
    for(const auto* matrix:{&matrices->first,&matrices->second}) for(int col=0;col<4;++col) for(int row=0;row<4;++row)
        if(std::abs((*matrix)[col][row])>std::numeric_limits<float>::max())
            throw std::runtime_error("Camera matrix exceeds renderer range");
    return std::make_pair(glm::mat4(matrices->first),glm::mat4(matrices->second));
}
static Vec2 CheckViewport(Vec2 viewport) {
    viewport=finite(viewport);
    if(viewport.x<=0 || viewport.y<=0) throw std::runtime_error("Camera viewport must be positive");
    return viewport;
}
Vec2 WorldToScreen(const Ctx& c,EntityRef id,Vec3 world,Vec2 viewport) {
    world=finite(world); viewport=CheckViewport(viewport);
    const auto matrices=CameraMatrices(c,id,viewport.x/viewport.y);
    if(!matrices) throw std::runtime_error("Camera is missing or inactive");
    const auto clip=matrices->second*matrices->first*glm::dvec4(world,1.0);
    if(!std::isfinite(clip.w) || std::abs(clip.w)<1e-12) throw std::runtime_error("World point cannot be projected");
    const auto ndc=glm::dvec3(clip)/clip.w;
    return finite(Vec2{(ndc.x+1.0)*.5*viewport.x,(1.0-ndc.y)*.5*viewport.y});
}
Vec3 ScreenToWorld(const Ctx& c,EntityRef id,Vec2 screen,double depth,Vec2 viewport) {
    screen=finite(screen); depth=finite(depth); viewport=CheckViewport(viewport);
    if(depth<0 || depth>1) throw std::runtime_error("Screen depth must be between 0 and 1");
    const auto matrices=CameraMatrices(c,id,viewport.x/viewport.y);
    if(!matrices) throw std::runtime_error("Camera is missing or inactive");
    const auto inverse=glm::inverse(matrices->second*matrices->first);
    const auto clip=glm::dvec4{screen.x/viewport.x*2.0-1.0,1.0-screen.y/viewport.y*2.0,depth,1.0};
    const auto world=inverse*clip;
    if(!std::isfinite(world.w) || std::abs(world.w)<1e-12) throw std::runtime_error("Screen point cannot be unprojected");
    return finite(glm::dvec3(world)/world.w);
}
bool IsEntityVisible(Ctx& c,EntityRef id) {
    auto e=Handle(c,id.id);
    while(e.id()) { if(!e.get<Mesh>().visible) return false; e=e.target(flecs::ChildOf); }
    return true;
}
void SetEntityVisibility(Ctx& c,EntityRef id,bool visible) { auto e=Handle(c,id.id); e.ensure<Mesh>().visible=visible; e.modified<Mesh>(); }
bool IsEntityActive(const Ctx& c,EntityRef id) {
    if(!EntityExists(c,id)) return false;
    for(auto e=Handle(c,id.id); e.id(); e=e.target(flecs::ChildOf))
        if(!e.get<Activity>().active) return false;
    return true;
}
bool GetEntityActiveSelf(Ctx& c,EntityRef id) { return Handle(c,id.id).get<Activity>().active; }
void SetEntityActive(Ctx& c,EntityRef id,bool active) {
    auto e=Handle(c,id.id); e.ensure<Activity>().active=active; e.modified<Activity>();
    RefreshEntityActivity(c);
}
static void Layer(std::int64_t layer) {
    if(layer<0 || layer>31) throw std::runtime_error("Entity layer must be an integer between 0 and 31");
}
std::int64_t GetEntityLayer(Ctx& c,EntityRef id) { return Handle(c,id.id).get<Activity>().layer; }
void SetEntityLayer(Ctx& c,EntityRef id,std::int64_t layer) {
    Layer(layer); auto e=Handle(c,id.id); e.ensure<Activity>().layer=layer; e.modified<Activity>();
}
Array<EntityRef> FindEntitiesByLayer(Ctx& c,std::int64_t layer,bool active_only) {
    Layer(layer); Array<EntityRef> result;
    World(c).world.each([&](const Identity& identity,const Activity& activity) {
        if(activity.layer==layer && (!active_only || IsEntityActive(c,{identity.id}))) result.push_back({identity.id});
    });
    std::sort(result.begin(),result.end(),[](const auto& a,const auto& b){return a.id<b.id;});
    return result;
}
void AddEntityTag(Ctx& c,EntityRef id,std::string tag) {
    Text(tag,128,"entity tag"); auto e=Handle(c,id.id); auto& tags=e.ensure<Tags>().values;
    if(!tags.contains(tag) && tags.size()>=256) throw std::runtime_error("At most 256 tags per entity are allowed");
    tags.insert(std::move(tag)); e.modified<Tags>();
}
void RemoveEntityTag(Ctx& c,EntityRef id,std::string tag) { Text(tag,128,"entity tag"); auto e=Handle(c,id.id); e.ensure<Tags>().values.erase(tag); e.modified<Tags>(); }
bool HasEntityTag(Ctx& c,EntityRef id,std::string tag) { Text(tag,128,"entity tag"); return Handle(c,id.id).get<Tags>().values.contains(tag); }
Array<EntityRef> FindEntitiesByTag(Ctx& c,std::string tag) {
    Text(tag,128,"entity tag"); Array<EntityRef> result;
    for(const auto& [id,handle]:World(c).index) if(World(c).world.entity(handle).get<Tags>().values.contains(tag)) result.push_back({id});
    return result;
}
std::vector<RenderEntity> RenderEntities(const Ctx& c) {
    std::vector<RenderEntity> result;
    auto& w=World(c);
    // Iterate Flecs component tables; spawned/cloned entities render immediately.
    w.world.each([&](const Identity& identity,const Mesh& mesh) {
        if(!IsEntityActive(c,{identity.id})) return;
        auto e=Handle(c,identity.id);
        for(auto p=e; p.id(); p=p.target(flecs::ChildOf)) if(!p.get<Mesh>().visible) return;
        const auto matrix=Matrix(c,identity.id);
        for(int col=0;col<4;++col) for(int row=0;row<4;++row)
            if(std::abs(matrix[col][row])>std::numeric_limits<float>::max()) throw std::runtime_error("Transform exceeds GPU float range");
        std::optional<MaterialParameters> material;
        const auto& binding=e.get<MaterialBinding>();
        if(!binding.asset.empty()) material=ResolveMaterial(binding,w.materials);
        const auto order=w.render_order.find(identity.id);
        const auto sorting_layer=order==w.render_order.end() ? std::string("default") : order->second.first;
        const auto sorting_order=order==w.render_order.end() ? 0 : order->second.second;
        if(!mesh.asset.empty()) result.push_back({identity.id,mesh.asset,sorting_layer,sorting_order,glm::mat4(matrix),material});
        const auto& sprite=e.get<SpriteBinding>();
        if(!sprite.asset.empty()) {
            const auto& asset=w.sprites.at(sprite.asset);
            const int columns=asset.at("columns"),rows=asset.at("rows");
            const float u=1.f/columns,v=1.f/rows;
            auto frame=sprite.frame; auto state=w.sprite_states.find(identity.id);
            if(state!=w.sprite_states.end()) frame=state->second.frame;
            glm::vec4 uv{sprite.flip_x ? -u : u,sprite.flip_y ? -v : v,
                (frame%columns+(sprite.flip_x ? 1 : 0))*u,
                (frame/columns+(sprite.flip_y ? 1 : 0))*v};
            result.push_back({identity.id,"@sprite:"+sprite.asset,sorting_layer,sorting_order,glm::mat4(matrix),material,uv,true});
        }
    });
    for(const auto& tilemap:w.tilemaps) {
        const auto id=tilemap.at("id").get<std::string>();
        const auto layer=tilemap.value("sorting_layer",std::string("default"));
        const auto order=tilemap.value("sorting_order",0LL);
        result.push_back({"@tilemap:"+id,"@tilemap:"+id,layer,order,glm::mat4(1.f),std::nullopt,glm::vec4(1,1,0,0),false});
    }
    std::sort(result.begin(),result.end(),[](const auto& a,const auto& b){
        return std::tie(a.sorting_layer,a.sorting_order,a.id,a.mesh)<std::tie(b.sorting_layer,b.sorting_order,b.id,b.mesh);
    });
    return result;
}
Json SceneEntities(const Ctx& c) {
    Json result=Json::array();
    for(const auto& [id,handle]:World(c).index) {
        auto e=World(c).world.entity(handle);
        const auto& transform=e.get<Entity>(); const auto& mesh=e.get<Mesh>();
        Json item={{"id",id},{"name",e.get<Identity>().name},{"position",vec_json(transform.position)},
            {"rotation",vec_json(transform.rotation)},{"scale",vec_json(transform.scale)},
            {"visible",mesh.visible},{"tags",e.get<Tags>().values},
            {"active",e.get<Activity>().active},{"layer",e.get<Activity>().layer}};
        const auto order=World(c).render_order.find(id);
        if(order!=World(c).render_order.end()) {
            item["sorting_layer"]=order->second.first;
            item["sorting_order"]=order->second.second;
        }
        auto parent=e.target(flecs::ChildOf);
        if(parent.id()) item["parent"]=parent.get<Identity>().id;
        if(!mesh.asset.empty()) item["mesh"]=mesh.asset;
        const auto& camera=e.get<Camera>();
        if(camera.present) item["camera"]=CameraJson(camera);
        const auto& material=e.get<MaterialBinding>();
        if(!material.asset.empty()) item["material"]=MaterialBindingJson(material);
        const auto& sprite=e.get<SpriteBinding>();
        if(!sprite.asset.empty()) item["sprite"]=SpriteBindingJson(sprite);
        if(const auto state=World(c).sprite_states.find(id); state!=World(c).sprite_states.end())
            item["sprite_state"]={{"asset",state->second.asset},{"state",state->second.state},
                {"frame",state->second.frame},{"elapsed",state->second.elapsed},{"playing",state->second.playing}};
        const auto& body=e.get<RigidBodyConfig>().value;
        if(!body.is_null()) item["rigid_body"]=body;
        Json components=Json::object();
        for(const auto& [cid,schema]:World(c).components) {
            if(!e.has<ComponentData>(schema.entity)) continue;
            const auto& data=e.get<ComponentData>(schema.entity);
            Json properties=Json::object();
            for(const auto& [fid,value]:data.properties)
                properties[std::to_string(fid)]=std::visit([](const auto& v){return ToJson(v);},value);
            components[std::to_string(cid)]={{"enabled",data.enabled},{"properties",properties}};
        }
        if(!components.empty()) item["components"]=components;
        result.push_back(std::move(item));
    }
    return result;
}
Json TransformSnapshot(const Ctx& c) {
    Json result=Json::object();
    for(const auto& [id,handle]:World(c).index) {
        const auto& e=World(c).world.entity(handle).get<Entity>();
        result[id]={{"position",vec_json(e.position)},{"rotation",vec_json(e.rotation)},{"scale",vec_json(e.scale)}};
    }
    return result;
}
Json ComponentDefinitions(const Ctx& c) {
    Json result=Json::array();
    for(const auto& [_,schema]:World(c).components) result.push_back(schema.definition);
    return result;
}
Json MaterialAssets(const Ctx& c) {
    Json result=Json::array();
    for(const auto& [_,asset]:World(c).materials) result.push_back(asset);
    return result;
}
bool MaterialExists(const Ctx& c,std::string id) { return World(c).materials.contains(id); }
std::string GetMaterial(Ctx& c,EntityRef id) { return Handle(c,id.id).get<MaterialBinding>().asset; }
void SetMaterial(Ctx& c,EntityRef id,std::string asset) {
    auto e=Handle(c,id.id);
    if(!MaterialExists(c,asset)) throw std::runtime_error("Unknown material asset: "+asset);
    e.set<MaterialBinding>({asset,Json::object()});
}
void ClearMaterial(Ctx& c,EntityRef id) { Handle(c,id.id).set<MaterialBinding>({}); }
void ResetMaterialParameters(Ctx& c,EntityRef id) {
    const auto asset=GetMaterial(c,id);
    if(asset.empty()) throw std::runtime_error("Entity has no assigned material");
    SetMaterial(c,id,asset);
}
static MaterialParameters MaterialValue(Ctx& c,EntityRef id) {
    return ResolveMaterial(Handle(c,id.id).get<MaterialBinding>(),World(c).materials);
}
static void WriteMaterial(Ctx& c,EntityRef id,const char* key,Json value) {
    auto e=Handle(c,id.id);
    auto binding=e.get<MaterialBinding>();
    if(binding.asset.empty()) throw std::runtime_error("Entity has no assigned material");
    binding.overrides[key]=std::move(value);
    CheckMaterialParameters(binding.overrides,true);
    e.set<MaterialBinding>(binding);
}
Vec3 GetMaterialColor(Ctx& c,EntityRef id) { return MaterialValue(c,id).color; }
void SetMaterialColor(Ctx& c,EntityRef id,Vec3 value) { WriteMaterial(c,id,"color",vec_json(finite(value))); }
double GetMaterialOpacity(Ctx& c,EntityRef id) { return MaterialValue(c,id).opacity; }
void SetMaterialOpacity(Ctx& c,EntityRef id,double value) { WriteMaterial(c,id,"opacity",finite(value)); }
std::string GetMaterialAlphaMode(Ctx& c,EntityRef id) { return MaterialValue(c,id).alpha_mode; }
void SetMaterialAlphaMode(Ctx& c,EntityRef id,std::string value) { WriteMaterial(c,id,"alpha_mode",value); }
double GetMaterialAlphaCutoff(Ctx& c,EntityRef id) { return MaterialValue(c,id).alpha_cutoff; }
void SetMaterialAlphaCutoff(Ctx& c,EntityRef id,double value) { WriteMaterial(c,id,"alpha_cutoff",finite(value)); }
bool IsMaterialUnlit(Ctx& c,EntityRef id) { return MaterialValue(c,id).unlit; }
void SetMaterialUnlit(Ctx& c,EntityRef id,bool value) { WriteMaterial(c,id,"unlit",value); }
Json SpriteAssets(const Ctx& c) {
    Json result=Json::array(); for(const auto& [_,asset]:World(c).sprites) result.push_back(asset); return result;
}
static const Json& SpriteStateAsset(const SceneWorld&,const std::string&);
bool SpriteExists(const Ctx& c,std::string asset) { return World(c).sprites.contains(asset); }
std::string GetSprite(Ctx& c,EntityRef id) { return Handle(c,id.id).get<SpriteBinding>().asset; }
void SetSprite(Ctx& c,EntityRef id,std::string asset) {
    auto e=Handle(c,id.id);
    if(!SpriteExists(c,asset)) throw std::runtime_error("Unknown sprite asset: "+asset);
    bool preserve_state=false;
    if(const auto state=World(c).sprite_states.find(id.id); state!=World(c).sprite_states.end())
        preserve_state=SpriteStateAsset(World(c),state->second.asset).at("sprite")==asset;
    e.set<SpriteBinding>({asset,0,false,false});
    if(!preserve_state) World(c).sprite_states.erase(id.id);
}
void ClearSprite(Ctx& c,EntityRef id) { Handle(c,id.id).set<SpriteBinding>({}); World(c).sprite_states.erase(id.id); }
static SpriteBinding SpriteValue(Ctx& c,EntityRef id) {
    auto binding=Handle(c,id.id).get<SpriteBinding>();
    if(binding.asset.empty()) throw std::runtime_error("Entity has no assigned sprite");
    return binding;
}
std::int64_t GetSpriteFrameCount(Ctx& c,EntityRef id) {
    const auto& asset=World(c).sprites.at(SpriteValue(c,id).asset);
    return asset.at("columns").get<int>()*asset.at("rows").get<int>();
}
std::int64_t GetSpriteFrame(Ctx& c,EntityRef id) { return SpriteValue(c,id).frame; }
void SetSpriteFrame(Ctx& c,EntityRef id,std::int64_t frame) {
    auto binding=SpriteValue(c,id);
    if(frame<0 || frame>=GetSpriteFrameCount(c,id)) throw std::runtime_error("Sprite frame is outside its atlas");
    binding.frame=frame; Handle(c,id.id).set<SpriteBinding>(binding);
    if(auto state=World(c).sprite_states.find(id.id); state!=World(c).sprite_states.end()) {
        state->second.frame=frame; state->second.elapsed=0;
    }
}
void SetSpriteFlip(Ctx& c,EntityRef id,bool x,bool y) {
    auto binding=SpriteValue(c,id); binding.flip_x=x; binding.flip_y=y; Handle(c,id.id).set<SpriteBinding>(binding);
}
bool GetSpriteFlipX(Ctx& c,EntityRef id) { return SpriteValue(c,id).flip_x; }
bool GetSpriteFlipY(Ctx& c,EntityRef id) { return SpriteValue(c,id).flip_y; }
static const Json& SpriteStateAsset(const SceneWorld& w,const std::string& id) {
    for(const auto& asset:w.sprite_state_assets) if(asset.at("id")==id) return asset;
    throw std::runtime_error("Unknown sprite state machine: "+id);
}
Json SpriteStateAssets(const Ctx& c) { return World(c).sprite_state_assets; }
void SetSpriteState(Ctx& c,EntityRef id,std::string state) {
    auto binding=SpriteValue(c,id);
    auto& w=World(c);
    std::string asset;
    if(auto current=w.sprite_states.find(id.id); current!=w.sprite_states.end()) asset=current->second.asset;
    else throw std::runtime_error("Entity has no sprite state machine");
    const auto& definition=SpriteStateAsset(w,asset);
    if(!definition.at("states").contains(state)) throw std::runtime_error("Unknown sprite state: "+state);
    if(definition.at("sprite")!=binding.asset) throw std::runtime_error("Sprite state machine sprite differs from entity sprite");
    const auto& frames=definition.at("states").at(state);
    auto& current=w.sprite_states[id.id]; current.state=std::move(state); current.frame=frames.at(0).get<std::int64_t>(); current.elapsed=0; current.playing=true;
}
std::string GetSpriteState(Ctx& c,EntityRef id) {
    auto it=World(c).sprite_states.find(id.id); if(it==World(c).sprite_states.end()) throw std::runtime_error("Entity has no sprite state machine");
    return it->second.state;
}
void AdvanceSpriteStates(Ctx& c) {
    if(!std::isfinite(c.dt) || c.dt<0) throw std::runtime_error("Invalid sprite state delta time");
    auto& w=World(c);
    for(auto it=w.sprite_states.begin();it!=w.sprite_states.end();) {
        if(!EntityExists(c,{it->first})) { it=w.sprite_states.erase(it); continue; }
        auto& current=it->second; const auto& machine=SpriteStateAsset(w,current.asset); const auto& frames=machine.at("states").at(current.state);
        if(current.playing && IsEntityActive(c,{it->first})) {
            const double step=1.0/machine.at("fps").get<double>(); current.elapsed+=c.dt;
            while(current.elapsed>=step && current.playing) {
                current.elapsed-=step;
                auto index=std::find(frames.begin(),frames.end(),current.frame);
                auto position=index==frames.end() ? 0 : static_cast<std::size_t>(index-frames.begin());
                if(position+1<frames.size()) current.frame=frames.at(position+1).get<std::int64_t>();
                else if(machine.at("loop").get<bool>()) current.frame=frames.at(0).get<std::int64_t>();
                else { current.frame=frames.back().get<std::int64_t>(); current.playing=false; current.elapsed=0; }
            }
        }
        ++it;
    }
}
Json TilemapAssets(const Ctx& c) { return World(c).tilemaps; }
Json FeatureMetadata(const Ctx& c) { return World(c).features; }
std::set<std::string> SceneMeshes(const Ctx& c) {
    auto result=World(c).assets;
    for(const auto& tilemap:World(c).tilemaps) result.insert("@tilemap:"+tilemap.at("id").get<std::string>());
    return result;
}
static Json OwnedPrefabComponents(flecs::entity e) {
    Json result=Json::array();
    if(e.owns<Entity>()) result.push_back("transform");
    if(e.owns<Mesh>()) result.push_back("mesh");
    if(e.owns<Tags>()) result.push_back("tags");
    if(e.owns<Activity>()) result.push_back("activity");
    const auto base=e.target(flecs::IsA);
    if(e.owns<Camera>() && (e.get<Camera>().present || base.id())) result.push_back("camera");
    if(e.owns<MaterialBinding>() && (!e.get<MaterialBinding>().asset.empty() || base.id())) result.push_back("material");
    if(e.owns<SpriteBinding>() && (!e.get<SpriteBinding>().asset.empty() || base.id())) result.push_back("sprite");
    if(e.owns<RigidBodyConfig>() && (!e.get<RigidBodyConfig>().value.is_null() || base.id())) result.push_back("rigid_body");
    return result;
}
static Json NativePrefabState(flecs::entity e) {
    Json result={{"is_prefab",e.has(flecs::Prefab)},{"owned_components",OwnedPrefabComponents(e)},{"base",nullptr}};
    auto base=e.target(flecs::IsA);
    if(base.id()) {
        const auto& identity=base.get<PrefabTemplate>();
        result["base"]={{"asset",identity.asset},{"local",identity.local}};
    }
    return result;
}
void SnapshotPrefabs(const Ctx& c,Json& scene,Json& snapshot) {
    auto& w=World(c);
    if(w.prefabs.empty()) return;
    scene["prefab_assets"]=w.prefab_assets;
    scene["prefab_templates"]=w.prefab_templates;
    scene["prefab_instances"]=Json::array();
    Json state={{"templates",Json::object()},{"entities",Json::object()}};
    for(const auto& [asset,prefab]:w.prefabs) for(const auto& [local,handle]:prefab.nodes)
        state["templates"][asset][local]=NativePrefabState(w.world.entity(handle));
    for(const auto& [root,instance]:w.instances) {
        Json owned=Json::object(), components=Json::object();
        for(const auto& [local,id]:instance.mapping) if(w.index.contains(id)) {
            auto e=Handle(c,id);
            owned[local]=OwnedPrefabComponents(e);
            state["entities"][id]=NativePrefabState(e);
            state["entities"][id]["root"]=root;
            if(instance.component_overrides.contains(local)) components[local]=instance.component_overrides.at(local);
        }
        scene["prefab_instances"].push_back({{"prefab",instance.asset},{"root",root},
            {"mapping",instance.mapping},{"owned_components",owned}});
        if(!instance.retired.empty()) scene["prefab_instances"].back()["retired"]=instance.retired;
        if(!components.empty()) scene["prefab_instances"].back()["component_overrides"]=components;
    }
    snapshot["prefab_state"]=std::move(state);
}
static void RecordComponentWrite(Ctx& c,EntityRef id,int component,const char* operation,int field=0) {
    auto e=Handle(c,id.id);
    if(!e.has<PrefabLink>()) return;
    const auto& link=e.get<PrefabLink>();
    auto& overrides=World(c).instances.at(link.root).component_overrides;
    auto& mask=overrides[link.local][std::to_string(component)];
    if(mask.is_null()) mask=Json::object();
    const std::string op=operation;
    if(op=="add" || op=="remove") mask=Json{{"present",op=="add"}};
    else if(op=="enable") mask["enabled"]=true;
    else {
        auto fields=mask.value("properties",Json::array());
        if(std::find(fields.begin(),fields.end(),field)==fields.end()) fields.push_back(field);
        std::sort(fields.begin(),fields.end());
        mask["properties"]=std::move(fields);
    }
}
void AddComponent(Ctx& c,EntityRef id,int component) {
    auto& schema=Component(c,component); auto e=Handle(c,id.id);
    if(e.has<ComponentData>(schema.entity)) return;
    ComponentData data;
    for(const auto& [fid,field]:schema.fields) data.properties.emplace(fid,field.initial);
    e.set<ComponentData>(schema.entity,data);
    RecordComponentWrite(c,id,component,"add");
}
void RemoveComponent(Ctx& c,EntityRef id,int component) {
    Handle(c,id.id).remove<ComponentData>(Component(c,component).entity);
    RecordComponentWrite(c,id,component,"remove");
}
bool HasComponent(Ctx& c,EntityRef id,int component) {
    auto handle=Component(c,component).entity;
    return EntityExists(c,id) && Handle(c,id.id).has<ComponentData>(handle);
}
void SetComponentEnabled(Ctx& c,EntityRef id,int component,bool enabled) {
    auto copy=Data(c,id,component); copy.enabled=enabled;
    Handle(c,id.id).set<ComponentData>(Component(c,component).entity,copy);
    RecordComponentWrite(c,id,component,"enable");
}
bool IsComponentEnabled(Ctx& c,EntityRef id,int component) { return HasComponent(c,id,component) && Data(c,id,component).enabled; }
Array<EntityRef> FindEntitiesWithComponent(Ctx& c,int component,bool enabled_only) {
    const auto handle=Component(c,component).entity;
    Array<EntityRef> result;
    auto query=World(c).world.query_builder().with<ComponentData>(handle).build();
    query.each([&](flecs::entity e) {
        if(!enabled_only || e.get<ComponentData>(handle).enabled) result.push_back({e.get<Identity>().id});
    });
    std::sort(result.begin(),result.end(),[](const auto& a,const auto& b){return a.id<b.id;});
    return result;
}
Value ReadComponentProperty(Ctx& c,EntityRef id,int component,int field) {
    const auto& properties=Data(c,id,component).properties;
    auto found=properties.find(field);
    if(found==properties.end()) throw std::runtime_error("Unknown component property");
    return found->second;
}
void WriteComponentProperty(Ctx& c,EntityRef id,int component,int field,Value value) {
    auto& schema=Component(c,component);
    auto found=schema.fields.find(field);
    if(found==schema.fields.end()) throw std::runtime_error("Unknown component property");
    std::visit([&](const auto& v) {
        if(TypeName<std::decay_t<decltype(v)>>()!=found->second.type) throw std::runtime_error("Component property type mismatch");
        CheckValue(v);
    },value);
    auto copy=Data(c,id,component); copy.properties[field]=std::move(value);
    Handle(c,id.id).set<ComponentData>(schema.entity,copy);
    RecordComponentWrite(c,id,component,"set",field);
}
Value DispatchComponent(Ctx& c,int type,const std::vector<Value>& args) {
    if(type<600100 || type>=1000000) throw std::runtime_error("Unknown runtime node type: "+std::to_string(type));
    const int component=(type-600000)/100, slot=(type-600000)%100;
    const bool property=slot>=12 && slot<=75;
    const std::size_t count=(slot==3 || (property && slot%2)) ? 2 : 1;
    if(args.size()!=count) throw std::runtime_error("Invalid component argument count");
    if(slot==5) return FindEntitiesWithComponent(c,component,std::get<bool>(args[0]));
    auto entity=std::get<EntityRef>(args[0]);
    switch(slot) {
        case 0: AddComponent(c,entity,component); break;
        case 1: RemoveComponent(c,entity,component); break;
        case 2: return HasComponent(c,entity,component);
        case 3: SetComponentEnabled(c,entity,component,std::get<bool>(args[1])); break;
        case 4: return IsComponentEnabled(c,entity,component);
        default:
            if(!property) throw std::runtime_error("Unknown component node operation");
            if(!(slot%2)) return ReadComponentProperty(c,entity,component,(slot-10)/2);
            WriteComponentProperty(c,entity,component,(slot-10)/2,args[1]);
    }
    return 0.;
}
}
