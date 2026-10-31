#include "prefab_edits.hpp"
#include "materials.hpp"
#include "sprites.hpp"
#include "physics_scene.hpp"
#include <functional>
#include <regex>

namespace rt {
namespace {
using Entities=std::map<std::string,Json>;
using Mapping=std::map<std::string,std::string>;
const std::vector<std::pair<std::string,std::vector<std::string>>> builtins={
    {"transform",{"position","rotation","scale"}}, {"mesh",{"mesh","visible"}},
    {"tags",{"tags"}}, {"activity",{"active","layer"}}, {"camera",{"camera"}}, {"material",{"material"}}, {"sprite",{"sprite"}}, {"rigid_body",{"rigid_body"}}};
const std::set<std::string> fields={"name","parent","position","rotation","scale","mesh",
                                    "visible","active","layer","tags","components","camera","material","sprite","rigid_body"};

void Require(bool condition,const std::string& message) {
    if(!condition) throw std::runtime_error(message);
}
void Known(const Json& value,const std::set<std::string>& allowed,const char* label) {
    Require(value.is_object(),std::string(label)+" must be an object");
    for(const auto& [key,_]:value.items()) Require(allowed.contains(key),std::string(label)+": unknown field "+key);
}
void Array(const Json& value,std::size_t limit,const char* label) {
    Require(value.is_array() && value.size()<=limit,std::string("Invalid ")+label+" or limit exceeded");
}
std::string Identifier(const Json& value) {
    static const std::regex pattern("[A-Za-z0-9_-]{1,48}");
    Require(value.is_string() && std::regex_match(value.get<std::string>(),pattern),"Invalid prefab asset/local ID");
    return value.get<std::string>();
}
Entities Index(const Json& array) {
    Entities result;
    for(const auto& item:array) Require(result.emplace(item.at("id").get<std::string>(),item).second,"Duplicate entity ID");
    return result;
}
Json Values(const Entities& values) {
    Json result=Json::array();
    for(const auto& [_,value]:values) result.push_back(value);
    return result;
}
template<class T> bool Contains(const Json& array,const T& value) {
    return std::find(array.begin(),array.end(),Json(value))!=array.end();
}
struct Library {
    Entities sources, templates, schemas;
    MaterialLibrary materials;
    SpriteLibrary sprites;
    explicit Library(const Json& assets,const Json& definitions,const Json& material_assets,const Json& sprite_assets) {
        materials=ReadMaterialAssets(material_assets);
        sprites=ReadSpriteAssets(sprite_assets);
        for(const auto& definition:definitions) schemas.emplace(std::to_string(definition.at("id").get<int>()),definition);
        Array(assets,1024,"prefab library");
        for(const auto& asset:assets) {
            Known(asset,{"version","type","id","name","root","entities","base","nested","overrides","removed","component_definitions","material_assets","sprite_assets"},"Prefab asset");
            MergeMaterialAssets(materials,asset.value("material_assets",Json::array()));
            MergeSpriteAssets(sprites,asset.value("sprite_assets",Json::array()));
            Require(asset.at("version").is_number_integer() && asset.at("version")==1 && asset.at("type")=="prefab","Unsupported prefab version/type");
            const auto aid=Identifier(asset.at("id"));
            Require(sources.emplace(aid,asset).second,"Duplicate prefab asset");
            Array(asset.value("entities",Json::array()),65536,"prefab entities");
            Array(asset.value("nested",Json::array()),65536,"nested prefabs");
            Array(asset.value("removed",Json::array()),65536,"prefab removals");
            std::set<std::string> used;
            for(const auto& schema:asset.value("component_definitions",Json::array())) {
                const auto cid=std::to_string(schema.at("id").get<int>());
                Require(used.insert(cid).second && schemas.contains(cid) && schemas.at(cid)==schema,"Conflicting prefab component definition");
            }
        }
        std::size_t total=0;
        for(const auto& [aid,_]:sources) {
            total+=Resolve(aid,{}).at("entities").size();
            Require(total<=65536,"Native prefab library exceeds 65536 template entities");
        }
    }
    Json Defaults(const std::string& cid) const {
        Require(schemas.contains(cid),"Unknown prefab component: "+cid);
        Json result={{"enabled",true},{"properties",Json::object()}};
        for(const auto& field:schemas.at(cid).at("properties")) {
            const auto type=field.at("type").get<std::string>();
            Json value=0;
            if(type=="bool") value=false;
            else if(type=="string" || type=="entity") value="";
            else if(type=="vec2") value=Json::array({0.,0.});
            else if(type=="vec3") value=Json::array({0.,0.,0.});
            else if(type=="vec4") value=Json::array({0.,0.,0.,0.});
            else if(type=="quat") value=Json::array({0.,0.,0.,1.});
            else if(type=="mat4") value=Json::array({1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.});
            else if(type.starts_with("array<")) value=Json::array();
            else if(type.starts_with("map<")) value=Json::object();
            result["properties"][std::to_string(field.at("id").get<int>())]=field.value("default",value);
        }
        return result;
    }
    Json Normalize(const Json& item) const {
        auto allowed=fields; allowed.insert("id"); Known(item,allowed,"Prefab entity");
        Json result={{"name",item.at("id")},{"parent",""},{"mesh",""},{"visible",true},
                     {"active",true},{"layer",0},{"tags",Json::array()},{"components",Json::object()},{"camera",nullptr},{"material",nullptr},{"sprite",nullptr},{"rigid_body",nullptr}};
        result.update(item);
        ReadMaterialBinding(result.at("material"),materials);
        ReadSpriteBinding(result.at("sprite"),sprites);
        if(!result.at("rigid_body").is_null()) (void)ReadAuthoredBody(result.at("rigid_body"));
        Array(result.at("tags"),256,"prefab tags");
        std::sort(result["tags"].begin(),result["tags"].end());
        Require(result.at("components").is_object(),"Prefab components must be an object");
        for(auto& [cid,instance]:result["components"].items()) {
            Known(instance,{"enabled","properties"},"Prefab component");
            auto complete=Defaults(cid);
            complete["enabled"]=instance.value("enabled",Json(true));
            Require(complete.at("enabled").is_boolean(),"Invalid component Enabled flag");
            auto props=instance.value("properties",Json::object());
            Require(props.is_object(),"Component properties must be an object");
            for(const auto& [key,value]:props.items()) {
                Require(complete.at("properties").contains(key),"Unknown component property");
                complete["properties"][key]=value;
            }
            for(const auto& field:schemas.at(cid).at("properties"))
                ValueFromJson(field.at("type"),complete.at("properties").at(std::to_string(field.at("id").get<int>())));
            instance=std::move(complete);
        }
        return result;
    }
    void References(Json& item,const std::function<std::string(const std::string&)>& remap) const {
        for(auto& [cid,instance]:item["components"].items()) for(const auto& field:schemas.at(cid).at("properties")) {
            auto& value=instance["properties"][std::to_string(field.at("id").get<int>())];
            const auto type=field.at("type").get<std::string>();
            if(type=="entity") value=remap(value.get<std::string>());
            else if(type=="array<entity>" || type=="map<entity>")
                for(auto& ref:value) ref=remap(ref.get<std::string>());
        }
    }
    void Patch(Entities& entities,const Json& patches) const {
        Require(patches.is_object(),"Prefab overrides must be an object");
        for(const auto& [local,patch]:patches.items()) {
            Require(entities.contains(local),"Override targets missing local entity: "+local);
            Known(patch,fields,"Prefab override");
            auto& target=entities.at(local);
            for(const auto& [prop,value]:patch.items()) {
                if(prop!="components") { target[prop]=value; continue; }
                Require(value.is_object(),"Component overrides must be an object");
                for(const auto& [cid,edit]:value.items()) {
                    auto defaults=Defaults(cid);
                    auto& components=target["components"];
                    if(edit.is_null()) {
                        Require(components.contains(cid),"Cannot remove absent prefab component");
                        components.erase(cid); continue;
                    }
                    Known(edit,{"enabled","properties"},"Component override");
                    if(!components.contains(cid)) components[cid]=std::move(defaults);
                    if(edit.contains("enabled")) components[cid]["enabled"]=edit.at("enabled");
                    if(edit.contains("properties")) {
                        Require(edit.at("properties").is_object(),"Property overrides must be an object");
                        components[cid]["properties"].update(edit.at("properties"));
                    }
                }
            }
            target=Normalize(target);
        }
    }
    void Tree(Entities& entities,const std::string& root,bool final) const {
        Require(!entities.empty() && entities.size()<=65536,"Invalid prefab entity count");
        if(final) Require(entities.contains(root),"Missing prefab root");
        for(auto& [local,item]:entities) {
            std::set<std::string> visited;
            for(auto current=local; !current.empty(); current=entities.at(current).at("parent").get<std::string>()) {
                Require(entities.contains(current),"Prefab parent targets missing entity");
                Require(visited.insert(current).second && visited.size()<=256,"Invalid prefab hierarchy or depth exceeds 256");
            }
            if(final) {
                Require(item.at("parent").get<std::string>().empty()==(local==root),"A prefab must have exactly one root");
                References(item,[&](const std::string& ref) {
                    Require(ref.empty() || entities.contains(ref),"Prefab reference targets missing local entity: "+ref);
                    return ref;
                });
            }
        }
    }
    const Json& Resolve(const std::string& aid,std::vector<std::string> chain) {
        Require(std::find(chain.begin(),chain.end(),aid)==chain.end(),"Prefab dependency cycle");
        Require(chain.size()<32,"Prefab dependency depth exceeds 32");
        Require(sources.contains(aid),"Missing prefab dependency: "+aid);
        if(templates.contains(aid)) {
            Require(chain.size()+templates.at(aid).at("dependency_depth").get<int>()<=32,"Prefab dependency depth exceeds 32");
            return templates.at(aid);
        }
        chain.push_back(aid);
        const auto& asset=sources.at(aid);
        Entities entities; Json bases=Json::object(); std::set<std::string> dependencies;
        int depth=1; std::string root;
        auto depend=[&](const std::string& id)->const Json& {
            const auto& resolved=Resolve(id,chain);
            dependencies.insert(id);
            for(const auto& dep:resolved.at("dependencies")) dependencies.insert(dep.get<std::string>());
            depth=std::max(depth,1+resolved.at("dependency_depth").get<int>());
            return resolved;
        };
        const auto base=asset.value("base",std::string{});
        if(!base.empty()) {
            const auto& resolved=depend(Identifier(base));
            entities=Index(resolved.at("entities")); root=resolved.at("root");
            Require(asset.value("root",root)==root,"Variant cannot replace inherited root ID");
            for(const auto& [local,_]:entities) bases[local]={{"asset",base},{"local",local}};
        } else root=Identifier(asset.at("root"));
        for(const auto& item:asset.value("entities",Json::array())) {
            auto local=Identifier(item.at("id"));
            Require(entities.emplace(local,Normalize(item)).second,"Duplicate prefab local ID; use overrides for inherited entities");
        }
        for(const auto& binding:asset.value("nested",Json::array())) {
            Known(binding,{"id","prefab","parent","overrides"},"Nested prefab binding");
            const auto prefix=Identifier(binding.at("id")), nested_id=Identifier(binding.at("prefab"));
            const auto& resolved=depend(nested_id); auto nested=Index(resolved.at("entities"));
            const auto nested_root=resolved.at("root").get<std::string>();
            Patch(nested,binding.value("overrides",Json::object())); Tree(nested,nested_root,true);
            Mapping mapping;
            for(const auto& [local,_]:nested) {
                mapping[local]=local==nested_root ? prefix : prefix+"/"+local;
                Require(!entities.contains(mapping.at(local)),"Nested prefab local ID collision");
            }
            for(auto& [local,item]:nested) {
                item["id"]=mapping.at(local);
                item["parent"]=local==nested_root ? binding.value("parent",std::string{}) : mapping.at(item.at("parent").get<std::string>());
                References(item,[&](const std::string& ref){return ref.empty() ? ref : mapping.at(ref);});
                entities.emplace(mapping.at(local),item);
                bases[mapping.at(local)]={{"asset",nested_id},{"local",local}};
            }
            Require(entities.size()<=65536,"Expanded prefab exceeds 65536 entities");
        }
        Patch(entities,asset.value("overrides",Json::object())); Tree(entities,root,false);
        std::set<std::string> removed;
        for(const auto& value:asset.value("removed",Json::array())) {
            auto local=value.get<std::string>();
            Require(local!=root && entities.contains(local) && removed.insert(local).second,"Invalid prefab removal");
        }
        bool changed=true;
        while(changed) {
            changed=false;
            for(const auto& [local,item]:entities)
                if(removed.contains(item.at("parent").get<std::string>())) changed=removed.insert(local).second || changed;
        }
        for(const auto& local:removed) { entities.erase(local); bases.erase(local); }
        Tree(entities,root,true);
        templates[aid]={{"id",aid},{"root",root},{"entities",Values(entities)},
                        {"dependencies",dependencies},{"dependency_depth",depth},{"bases",bases}};
        return templates.at(aid);
    }
    Json Compiled() const {
        auto result=Values(templates);
        std::sort(result.begin(),result.end(),[](const Json& a,const Json& b) {
            return std::pair{a.at("dependency_depth").get<int>(),a.at("id").get<std::string>()}<
                   std::pair{b.at("dependency_depth").get<int>(),b.at("id").get<std::string>()};
        });
        return result;
    }
    Entities Instantiate(const std::string& aid,const Mapping& mapping) const {
        auto entities=Index(templates.at(aid).at("entities")); Entities result;
        for(auto& [local,item]:entities) {
            item["id"]=mapping.at(local);
            auto parent=item.at("parent").get<std::string>(); item["parent"]=parent.empty() ? parent : mapping.at(parent);
            References(item,[&](const std::string& ref){return ref.empty() ? ref : mapping.at(ref);});
            result.emplace(mapping.at(local),std::move(item));
        }
        return result;
    }
};

std::set<std::string> Descendants(const Entities& entities,const Json& record) {
    std::map<std::string,std::vector<std::string>> children;
    for(const auto& [id,item]:entities) children[item.at("parent").get<std::string>()].push_back(id);
    std::vector<std::string> pending;
    for(const auto& id:record.at("mapping")) pending.push_back(id.get<std::string>());
    std::set<std::string> result;
    for(std::size_t i=0;i<pending.size();++i) {
        const auto id=pending[i];
        if(result.insert(id).second) for(const auto& child:children[id]) pending.push_back(child);
    }
    return result;
}
Json Owned(const Json& record,const std::string& local,const Json& current,const Json& before) {
    const auto explicit_=record.value("owned_components",Json::object()).value(local,Json::array());
    Json result=Json::array();
    for(const auto& [group,props]:builtins)
        if(Contains(explicit_,group) || std::any_of(props.begin(),props.end(),[&](const auto& p){return current.at(p)!=before.at(p);})) result.push_back(group);
    return result;
}
Json MergeComponents(const Json& before,const Json& current,Json updated,const Json& masks) {
    std::set<std::string> ids;
    for(const auto* set:{&before,&current,&masks}) for(const auto& [cid,_]:set->items()) ids.insert(cid);
    for(const auto& cid:ids) {
        const auto mask=masks.value(cid,Json::object());
        if(mask.contains("present")) {
            if(mask.at("present").get<bool>()) updated[cid]=current.at(cid);
            else updated.erase(cid);
        } else if(!current.contains(cid)) updated.erase(cid);
        else if(!before.contains(cid)) updated[cid]=current.at(cid);
        else if(!mask.empty() || current.at(cid)!=before.at(cid)) {
            if(!updated.contains(cid)) { updated[cid]=current.at(cid); continue; }
            const auto& old=before.at(cid); const auto& own=current.at(cid);
            if(mask.value("enabled",false) || own.at("enabled")!=old.at("enabled")) updated[cid]["enabled"]=own.at("enabled");
            for(const auto& [key,value]:own.at("properties").items())
                if(Contains(mask.value("properties",Json::array()),std::stoi(key)) || value!=old.at("properties").at(key)) updated[cid]["properties"][key]=value;
        }
    }
    return updated;
}
Json Delta(const Json& before,const Json& after,const Json& masks) {
    Json patch=Json::object(), components=Json::object(); std::set<std::string> ids;
    for(const auto& [prop,value]:after.items()) if(prop!="id" && prop!="components" && value!=before.at(prop)) patch[prop]=value;
    for(const auto* set:{&before.at("components"),&after.at("components")}) for(const auto& [cid,_]:set->items()) ids.insert(cid);
    for(const auto& cid:ids) {
        const auto& old=before.at("components"); const auto& own=after.at("components");
        const auto mask=masks.value(cid,Json::object());
        if(!own.contains(cid)) components[cid]=nullptr;
        else if(!old.contains(cid) || mask.value("present",false)) components[cid]=own.at(cid);
        else {
            Json edit=Json::object(), props=Json::object();
            if(mask.value("enabled",false) || old.at(cid).at("enabled")!=own.at(cid).at("enabled")) edit["enabled"]=own.at(cid).at("enabled");
            for(const auto& [key,value]:own.at(cid).at("properties").items())
                if(Contains(mask.value("properties",Json::array()),std::stoi(key)) || value!=old.at(cid).at("properties").at(key)) props[key]=value;
            if(!props.empty()) edit["properties"]=props;
            if(!edit.empty()) components[cid]=edit;
        }
    }
    if(!components.empty()) patch["components"]=components;
    return patch;
}
void Combine(Json& existing,const Json& changes) {
    if(existing.is_null()) existing=Json::object();
    for(const auto& [prop,value]:changes.items()) {
        if(prop!="components") { existing[prop]=value; continue; }
        for(const auto& [cid,edit]:value.items()) {
            auto& target=existing["components"][cid];
            if(edit.is_null() || target.is_null()) target=edit;
            else {
                if(edit.contains("enabled")) target["enabled"]=edit.at("enabled");
                if(edit.contains("properties")) {
                    if(!target.contains("properties")) target["properties"]=Json::object();
                    target["properties"].update(edit.at("properties"));
                }
            }
        }
    }
}
}

Json PlanPrefabApply(const Json& scene,const std::string& root,bool keep_placement,
                     const std::set<std::string>& reserved,std::uint64_t serial) {
    const auto definitions=scene.value("component_definitions",Json::array());
    const auto materials=scene.value("material_assets",Json::array());
    const auto sprites=scene.value("sprite_assets",Json::array());
    Library old(scene.at("prefab_assets"),definitions,materials,sprites);
    auto original=Index(scene.at("entities"));
    for(auto& [_,item]:original) item=old.Normalize(item);
    const auto& records=scene.at("prefab_instances");
    auto found=std::find_if(records.begin(),records.end(),[&](const Json& r){return r.at("root")==root;});
    Require(found!=records.end() && original.contains(root),"Apply requires a live prefab instance member");
    const auto& source=*found; const auto aid=source.at("prefab").get<std::string>();
    auto previous=Index(old.templates.at(aid).at("entities"));
    auto selected=Descendants(original,source);
    std::erase_if(selected,[&](const auto& id){return !original.contains(id);});
    Entities nested;
    for(const auto& record:records) if(record.at("root")!=root) {
        bool intersects=false, outside=false;
        for(const auto& value:record.at("mapping")) {
            const auto id=value.get<std::string>();
            intersects=intersects || selected.contains(id);
            outside=outside || (original.contains(id) && !selected.contains(id));
        }
        if(intersects) {
            const auto rid=record.at("root").get<std::string>();
            Require(selected.contains(rid) && !outside,"Apply contains only part of another prefab instance; reparent its members together");
            nested[rid]=record;
        }
    }
    Mapping reverse, adopted;
    std::set<std::string> locals;
    for(const auto& [local,id]:source.at("mapping").items()) { reverse[id.get<std::string>()]=local; locals.insert(local); }
    const auto source_retired=source.value("retired",Json::object());
    for(const auto& [local,_]:source_retired.items()) locals.insert(local);
    auto assets=old.sources;
    auto& asset=assets.at(aid);
    for(const auto& item:asset.value("entities",Json::array())) locals.insert(item.at("id").get<std::string>());
    for(const auto& binding:asset.value("nested",Json::array())) locals.insert(binding.at("id").get<std::string>());
    for(const auto& [_,t]:old.templates) for(const auto& item:t.at("entities")) locals.insert(item.at("id").get<std::string>());
    Json masks=source.value("component_overrides",Json::object()), captured_owned=Json::object();
    std::map<std::string,Mapping> nested_mappings;
    std::size_t nested_serial=0;
    for(const auto& [rid,record]:nested) {
        std::string prefix;
        do { prefix="nested_"+std::to_string(++nested_serial); } while(locals.contains(prefix));
        locals.insert(prefix);
        const auto& t=old.templates.at(record.at("prefab").get<std::string>());
        Mapping mapping;
        auto members=record.value("retired",Json::object()); members.update(record.at("mapping"));
        for(const auto& [local,value]:members.items()) {
            const auto id=value.get<std::string>();
            mapping[local]=local==t.at("root").get<std::string>() ? prefix : prefix+"/"+local;
            adopted[mapping.at(local)]=id;
            if(record.at("mapping").contains(local)) reverse[id]=mapping.at(local);
        }
        const auto component_masks=record.value("component_overrides",Json::object());
        const auto owned_components=record.value("owned_components",Json::object());
        for(const auto& [local,mask]:component_masks.items()) masks[mapping.at(local)]=mask;
        for(const auto& [local,owned]:owned_components.items()) captured_owned[mapping.at(local)]=owned;
        nested_mappings[rid]=std::move(mapping);
    }
    std::size_t local_serial=0;
    for(const auto& id:selected) if(!reverse.contains(id)) {
        std::string local;
        do { local="added_"+std::to_string(++local_serial); } while(locals.contains(local));
        locals.insert(local); reverse[id]=local; adopted[local]=id;
    }
    auto local_reference=[&](const std::string& ref) {
        if(ref.empty()) return ref;
        Require(selected.contains(ref),"External or deleted entity reference; repair it before Apply: "+ref);
        return reverse.at(ref);
    };
    for(const auto& [rid,record]:nested) {
        const auto nested_id=record.at("prefab").get<std::string>();
        const auto& t=old.templates.at(nested_id);
        const auto& mapping=nested_mappings.at(rid);
        const auto nested_root=t.at("root").get<std::string>();
        const auto parent=local_reference(original.at(rid).at("parent").get<std::string>());
        Require(!parent.empty(),"Reparent detached nested prefab roots into the instance before Apply");
        if(!asset.contains("nested")) asset["nested"]=Json::array();
        asset["nested"].push_back({{"id",mapping.at(nested_root)},{"prefab",nested_id},{"parent",parent}});
        auto baseline=old.Instantiate(nested_id,mapping);
        baseline.at(mapping.at(nested_root))["parent"]=parent;
        previous.insert(baseline.begin(),baseline.end());
    }
    Entities desired;
    std::set<int> used;
    for(const auto& definition:asset.value("component_definitions",Json::array())) used.insert(definition.at("id").get<int>());
    for(const auto& id:selected) {
        auto item=original.at(id); const auto local=reverse.at(id);
        item["id"]=local;
        item["parent"]=id==root ? "" : local_reference(item.at("parent").get<std::string>());
        Require(id==root || item.at("parent")!="","Reparent detached prefab members into the instance before Apply");
        old.References(item,local_reference);
        if(id==root && keep_placement) for(const auto& prop:builtins[0].second) item[prop]=previous.at(local).at(prop);
        for(const auto& [cid,_]:item.at("components").items()) used.insert(std::stoi(cid));
        desired[local]=std::move(item);
    }
    asset["component_definitions"]=Json::array();
    for(int cid:used) asset["component_definitions"].push_back(old.schemas.at(std::to_string(cid)));
    for(const auto& [local,item]:desired) {
        if(!previous.contains(local)) {
            if(!asset.contains("entities")) asset["entities"]=Json::array();
            asset["entities"].push_back(item);
        } else {
            auto changes=Delta(previous.at(local),item,masks.value(local,Json::object()));
            for(const auto& [group,props]:builtins) if(Contains(captured_owned.value(local,Json::array()),group))
                for(const auto& prop:props) changes[prop]=item.at(prop);
            if(!changes.empty()) Combine(asset["overrides"][local],changes);
        }
    }
    std::set<std::string> removed=asset.value("removed",std::set<std::string>{});
    for(const auto& [local,_]:previous) if(!desired.contains(local)) removed.insert(local);
    if(!removed.empty()) asset["removed"]=removed;
    std::set<std::string> used_materials;
    for(const auto& [_,item]:desired) if(!item.at("material").is_null()) used_materials.insert(item.at("material").at("asset").get<std::string>());
    for(const auto& material:asset.value("material_assets",Json::array())) used_materials.insert(material.at("id").get<std::string>());
    if(!used_materials.empty()) {
        asset["material_assets"]=Json::array();
        for(const auto& id:used_materials) asset["material_assets"].push_back(old.materials.at(id));
    }
    std::set<std::string> used_sprites;
    for(const auto& [_,item]:desired) if(!item.at("sprite").is_null()) used_sprites.insert(item.at("sprite").at("asset").get<std::string>());
    for(const auto& sprite:asset.value("sprite_assets",Json::array())) used_sprites.insert(sprite.at("id").get<std::string>());
    if(!used_sprites.empty()) {
        asset["sprite_assets"]=Json::array();
        for(const auto& id:used_sprites) asset["sprite_assets"].push_back(old.sprites.at(id));
    }
    Library updated(Values(assets),definitions,materials,sprites);
    Json result=scene; auto live=original; auto allocated=reserved;
    Json next_records=Json::array(); std::set<std::string> erased;
    for(const auto& record:records) {
        const auto rid=record.at("root").get<std::string>(), asset_id=record.at("prefab").get<std::string>();
        if(nested.contains(rid)) continue;
        const auto& next=updated.templates.at(asset_id);
        Require(next.at("root")==old.templates.at(asset_id).at("root"),"Instantiated prefab cannot replace its root ID");
        const auto prior_mapping=record.at("mapping").get<Mapping>();
        auto before=old.Instantiate(asset_id,prior_mapping);
        Mapping mapping, retired=record.value("retired",Mapping{});
        if(rid==root) {
            const auto next_entities=Index(next.at("entities"));
            for(const auto& [local,id]:adopted) if(!next_entities.contains(local)) retired[local]=id;
        }
        for(const auto& item:next.at("entities")) {
            const auto local=item.at("id").get<std::string>();
            if(prior_mapping.contains(local)) mapping[local]=prior_mapping.at(local);
            else if(rid==root && adopted.contains(local)) mapping[local]=adopted.at(local);
            else if(retired.contains(local)) { mapping[local]=retired.at(local); retired.erase(local); }
            else {
                std::string id;
                do {
                    Require(serial<static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()),"Entity ID sequence exhausted");
                    id="spawned_"+std::to_string(++serial);
                } while(allocated.contains(id));
                allocated.insert(id); mapping[local]=id;
            }
        }
        for(const auto& [local,id]:prior_mapping) if(!mapping.contains(local)) { retired[local]=id; erased.insert(id); }
        auto targets=updated.Instantiate(asset_id,mapping);
        if(rid==root) {
            auto descendants=Descendants(original,record);
            for(const auto& [_,id]:mapping) descendants.erase(id);
            erased.insert(descendants.begin(),descendants.end());
        }
        Json ownership=Json::object(), masks=Json::object();
        for(const auto& [local,id]:mapping) {
            if(!original.contains(id) && prior_mapping.contains(local) && rid!=root) continue;
            auto target=targets.at(id); Json owned=Json::array();
            if(original.contains(id) && before.contains(id) && rid!=root) {
                const auto& current=original.at(id); const auto& prior=before.at(id);
                owned=Owned(record,local,current,prior);
                for(const auto& [group,props]:builtins) if(Contains(owned,group)) for(const auto& prop:props) target[prop]=current.at(prop);
                for(const auto* prop:{"name","parent"}) if(current.at(prop)!=prior.at(prop)) target[prop]=current.at(prop);
                const auto mask=record.value("component_overrides",Json::object()).value(local,Json::object());
                target["components"]=MergeComponents(prior.at("components"),current.at("components"),target.at("components"),mask);
                if(!mask.empty()) masks[local]=mask;
            }
            if(id==rid) {
                const auto& current=original.at(id); target["parent"]=current.at("parent");
                if(keep_placement) {
                    bool displaced=false;
                    for(const auto& prop:builtins[0].second) { displaced=displaced || target.at(prop)!=current.at(prop); target[prop]=current.at(prop); }
                    if((displaced || Contains(Owned(record,local,current,before.at(id)),std::string("transform"))) && !Contains(owned,std::string("transform"))) owned.insert(owned.begin(),"transform");
                }
            }
            ownership[local]=owned; live[id]=std::move(target);
        }
        Json next_record={{"prefab",asset_id},{"root",rid},{"mapping",mapping},{"owned_components",ownership}};
        if(!retired.empty()) next_record["retired"]=retired;
        if(!masks.empty()) next_record["component_overrides"]=masks;
        next_records.push_back(std::move(next_record));
    }
    std::set<std::string> suppressed;
    for(const auto& record:next_records) for(const auto& id:record.at("mapping")) if(!live.contains(id.get<std::string>())) suppressed.insert(id.get<std::string>());
    bool changed=true;
    while(changed) {
        changed=false;
        for(auto it=live.begin();it!=live.end();) {
            if(!original.contains(it->first) && suppressed.contains(it->second.at("parent").get<std::string>())) {
                suppressed.insert(it->first); it=live.erase(it); changed=true;
            } else ++it;
        }
    }
    changed=true;
    while(changed) {
        auto count=erased.size();
        for(const auto& record:next_records) if(erased.contains(record.at("root").get<std::string>())) {
            auto descendants=Descendants(original,record); erased.insert(descendants.begin(),descendants.end());
        }
        changed=count!=erased.size();
    }
    for(const auto& id:erased) live.erase(id);
    for(auto& [_,item]:live) {
        std::set<std::string> visited;
        while(erased.contains(item.at("parent").get<std::string>())) {
            const auto parent=item.at("parent").get<std::string>();
            Require(visited.insert(parent).second,"Removed prefab parent chain has a cycle");
            item["parent"]=original.contains(parent) ? original.at(parent).at("parent") : Json("");
        }
    }
    for(auto it=next_records.begin();it!=next_records.end();) {
        if(!live.contains(it->at("root").get<std::string>())) it=next_records.erase(it);
        else {
            // Tombstones have no live ownership, including newly suppressed descendants.
            for(auto own=(*it)["owned_components"].begin();own!=(*it)["owned_components"].end();)
                if(!live.contains(it->at("mapping").at(own.key()).get<std::string>())) own=(*it)["owned_components"].erase(own); else ++own;
            ++it;
        }
    }
    result["entities"]=Values(live); result["prefab_assets"]=Values(assets);
    result["prefab_templates"]=updated.Compiled(); result["prefab_instances"]=std::move(next_records);
    result["entity_serial"]=serial;
    const auto selected_camera=result.value("active_camera",std::string{});
    if(!selected_camera.empty() && (!live.contains(selected_camera) || live.at(selected_camera).at("camera").is_null())) result.erase("active_camera");
    return result;
}
}
