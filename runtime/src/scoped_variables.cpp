#include "runtime.hpp"

namespace rt {
namespace {
void require(bool okay,const std::string& message) { if(!okay) throw std::runtime_error(message); }
std::string scope_of(const Ctx& c,const std::string& name) {
    const auto found=c.variable_scopes.find(name);
    return found==c.variable_scopes.end() ? "scene" : found->second;
}
bool compatible(const Value& a,const Value& b) {
    return ValueType(a)==ValueType(b);
}
void type_check(const std::string& name,const Value& expected,const Value& value) {
    require(compatible(expected,value),"Variable type mismatch: "+name);
}
Value unpack(const Json& value) {
    if(value.is_number()) return FromJson<double>(value);
    require(value.is_object() && value.size()==2 && value.contains("type") && value.contains("value"),"Invalid variable declaration");
    return ValueFromJson(value.at("type").get<std::string>(),value.at("value"));
}
VariableStore read_store(const Ctx& c,const Json& data) {
    require(data.is_object() && data.size()<=65536,"Variable storage requires an object of at most 65536 values");
    VariableStore result;
    for(const auto& [name,value]:data.items()) {
        VariableName(name); auto parsed=unpack(value); ValidateStoredUserValue(c,parsed);
        result.emplace(name,std::move(parsed));
    }
    return result;
}
const Value& lookup(const VariableStore& store,const std::string& name) {
    const auto found=store.find(name);
    require(found!=store.end(),"Variable not initialized: "+name);
    return found->second;
}
Json packed(const VariableStore& store) {
    Json result=Json::object();
    for(const auto& [name,value]:store) result[name]=VariableJson(value);
    return result;
}
}
const Value& GetScopedVariableValue(const Ctx& c,const std::string& scope,const std::string& name,EntityRef owner) {
    VariableName(name);
    if(scope=="global") return lookup(c.global_variables,name);
    if(scope=="scene") return lookup(c.variables,name);
    require(scope=="entity","Unknown variable scope: "+scope);
    require(EntityExists(c,owner),"Entity variable owner does not exist: "+owner.id);
    if(const auto entity=c.entity_variables.find(owner.id);entity!=c.entity_variables.end())
        if(const auto found=entity->second.find(name);found!=entity->second.end()) return found->second;
    return lookup(c.entity_variable_defaults,name);
}
void SetScopedVariableValue(Ctx& c,const std::string& scope,const std::string& name,Value value,EntityRef owner) {
    VariableName(name); std::visit([](const auto& item){CheckValue(item);},value);
    ValidateStoredUserValue(c,value);
    VariableStore* store;
    if(scope=="global") store=&c.global_variables;
    else if(scope=="scene") store=&c.variables;
    else {
        require(scope=="entity","Unknown variable scope: "+scope);
        require(EntityExists(c,owner),"Entity variable owner does not exist: "+owner.id);
        if(const auto found=c.entity_variable_defaults.find(name);found!=c.entity_variable_defaults.end()) type_check(name,found->second,value);
        store=&c.entity_variables[owner.id];
    }
    if(const auto found=store->find(name);found!=store->end()) type_check(name,found->second,value);
    require(store->contains(name) || store->size()<65536,"Variable storage exceeds 65536 values");
    store->insert_or_assign(name,std::move(value));
}
const Value& GetVariableValue(const Ctx& c,const std::string& name) {
    return GetScopedVariableValue(c,scope_of(c,name),name,{c.self});
}
void SetVariableValue(Ctx& c,const std::string& name,Value value) {
    SetScopedVariableValue(c,scope_of(c,name),name,std::move(value),{c.self});
}
void LoadVariableState(Ctx& c,const Json& scene) {
    c.variables.clear(); c.global_variables.clear(); c.entity_variables.clear();
    c.entity_variable_defaults.clear(); c.variable_scopes.clear();
    const auto values=read_store(c,scene.at("variables"));
    const auto scopes=scene.value("variable_scopes",Json::object());
    require(scopes.is_object(),"variable_scopes must be an object");
    for(const auto& [name,scope]:scopes.items()) {
        require(values.contains(name) && scope.is_string(),"Scope must reference a declared variable: "+name);
        const auto text=scope.get<std::string>();
        require(text=="scene" || text=="global" || text=="entity","Unknown variable scope: "+text);
        c.variable_scopes.emplace(name,text);
    }
    for(const auto& [name,value]:values) {
        const auto scope=scope_of(c,name);
        if(scope=="global") c.global_variables[name]=value;
        else if(scope=="entity") c.entity_variable_defaults[name]=value;
        else c.variables[name]=value;
    }
    if(scene.contains("global_variables")) {
        auto restored=read_store(c,scene.at("global_variables"));
        for(const auto& [name,value]:c.global_variables) {
            type_check(name,value,lookup(restored,name));
            require(VariableJson(value)==VariableJson(restored.at(name)),"Global variable snapshot disagrees with declaration: "+name);
        }
        c.global_variables=std::move(restored);
    }
    if(scene.contains("scene_variables")) {
        auto shadowed=read_store(c,scene.at("scene_variables"));
        for(auto& [name,value]:shadowed) {
            require(scope_of(c,name)!="scene","Redundant scene variable state: "+name);
            c.variables.emplace(name,std::move(value));
        }
    }
    if(scene.contains("entity_variables")) {
        const auto& entities=scene.at("entity_variables");
        require(entities.is_object() && entities.size()<=65536,"Invalid entity variable storage");
        for(const auto& [owner,entries]:entities.items()) {
            require(EntityExists(c,{owner}),"Entity variable owner does not exist: "+owner);
            auto restored=read_store(c,entries);
            for(const auto& [name,value]:restored)
                if(const auto found=c.entity_variable_defaults.find(name);found!=c.entity_variable_defaults.end()) type_check(name,found->second,value);
            c.entity_variables.emplace(owner,std::move(restored));
        }
    }
}
void SnapshotVariableState(const Ctx& c,Json& scene) {
    Json shadowed=Json::object();
    for(const auto& [name,value]:c.variables) if(scope_of(c,name)!="scene") shadowed[name]=VariableJson(value);
    if(!shadowed.empty()) scene["scene_variables"]=std::move(shadowed);
    for(const auto& [name,scope]:c.variable_scopes)
        if(scope=="global") scene["variables"][name]=VariableJson(lookup(c.global_variables,name));
    for(const auto& [name,value]:c.entity_variable_defaults) scene["variables"][name]=VariableJson(value);
    if(!c.variable_scopes.empty()) scene["variable_scopes"]=c.variable_scopes;
    if(!c.global_variables.empty()) scene["global_variables"]=packed(c.global_variables);
    if(!c.entity_variables.empty()) {
        auto values=Json::object();
        for(const auto& [owner,entries]:c.entity_variables) {
            require(EntityExists(c,{owner}),"Stale entity variable owner: "+owner);
            if(!entries.empty()) values[owner]=packed(entries);
        }
        if(!values.empty()) scene["entity_variables"]=std::move(values);
    }
}
void InitializeProjectGlobals(Ctx& c,const Json& program) {
    VariableStore definitions;
    const auto visit=[&](const Json& p) {
        const auto& scene=p.at("scene");
        const auto scopes=scene.value("variable_scopes",Json::object());
        require(scopes.is_object(),"variable_scopes must be an object");
        for(const auto& [name,scope]:scopes.items()) if(scope=="global") {
            VariableName(name); const auto value=unpack(scene.at("variables").at(name));
            if(const auto found=definitions.find(name);found!=definitions.end())
                require(VariableJson(found->second)==VariableJson(value),"Conflicting global declaration: "+name);
            else {
                require(definitions.size()<65536,"Global variable declarations exceed 65536 values");
                definitions.emplace(name,value);
            }
        }
    };
    if(program.contains("scenes")) for(const auto& p:program.at("scenes")) visit(p);
    else visit(program);
    for(const auto& [name,value]:definitions) {
        if(const auto found=c.global_variables.find(name);found!=c.global_variables.end()) type_check(name,value,found->second);
        else c.global_variables.emplace(name,value);
    }
}
}
