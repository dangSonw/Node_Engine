#include "runtime.hpp"

namespace rt {
namespace {
void check(bool okay,const std::string& message) { if(!okay) throw std::runtime_error(message); }
const Json& definition(const Ctx& c,const std::string& group,const std::string& name) {
    for(const auto& entry:c.user_types.at(group)) if(entry.at("name")==name) return entry;
    throw std::runtime_error("Unknown user type: "+name);
}
void validate(const Ctx& c,const std::string& type,const Json& value,int depth=0) {
    check(depth<=32,"User value nesting exceeds 32");
    for(const std::string kind:{"array","map","set"}) if(type.starts_with(kind+"<") && type.ends_with(">")) {
        const auto element=type.substr(kind.size()+1,type.size()-kind.size()-2);
        if(!element.starts_with("struct:") && !element.starts_with("enum:")) break;
        check(kind=="map" ? value.is_object() : value.is_array(),"Expected "+type);
        CollectionSize(value.size());
        // Validate the declaration even when the collection has no elements.
        definition(c,element.starts_with("struct:") ? "structs" : "enums",element.substr(element.find(':')+1));
        for(auto it=value.begin();it!=value.end();++it) {
            if(kind=="map") CheckValue(it.key());
            validate(c,element,it.value(),depth+1);
        }
        if(kind=="set") for(std::size_t i=0;i<value.size();++i) for(std::size_t j=0;j<i;++j)
            check(value.at(i)!=value.at(j),"Set contains duplicate elements");
        return;
    }
    if(type.starts_with("struct:")) {
        const auto& fields=definition(c,"structs",type.substr(7)).at("fields");
        check(value.is_object() && value.size()==fields.size(),"Expected fields of "+type);
        for(const auto& field:fields) {
            const auto name=field.at("name").get<std::string>();
            check(value.contains(name),"Struct field is missing: "+name);
            validate(c,field.at("type").get<std::string>(),value.at(name),depth+1);
        }
    } else if(type.starts_with("enum:")) {
        check(value.is_string(),"Expected enum label for "+type);
        const auto& values=definition(c,"enums",type.substr(5)).at("values");
        for(const auto& item:values) if((item.is_string() ? item : item.at("name"))==value) return;
        throw std::runtime_error("Unknown "+type+" label: "+value.get<std::string>());
    } else {
        ValueFromJson(type,value);
    }
}
}
Value CheckedValueFromJson(const Ctx& c,const std::string& type,const Json& value) {
    validate(c,type,value);
    return ValueFromJson(type,value);
}
void ValidateTypedValue(const Ctx& c,const std::string& type,const Value& value) {
    check(ValueType(value)==type,"Function value type mismatch: expected "+type);
    std::visit([&](const auto& item) {
        using T=std::decay_t<decltype(item)>;
        if constexpr(std::is_same_v<T,StructValue>) validate(c,type,item.fields);
        else if constexpr(std::is_same_v<T,EnumValue>) validate(c,type,item.value);
        else if constexpr(std::is_same_v<T,UserCollectionValue>) validate(c,type,item.items);
        else CheckValue(item);
    },value);
}
void ValidateStoredUserValue(const Ctx& c,const Value& value) {
    if(const auto* item=std::get_if<UserCollectionValue>(&value)) { validate(c,item->type,item->items); return; }
    if(const auto* item=std::get_if<StructValue>(&value)) {
        for(const auto& entry:c.user_types.at("structs")) if("struct:"+entry.at("name").get<std::string>()==item->type) {
            validate(c,item->type,item->fields); return;
        }
    } else if(const auto* item=std::get_if<EnumValue>(&value)) {
        for(const auto& entry:c.user_types.at("enums")) if("enum:"+entry.at("name").get<std::string>()==item->type) {
            validate(c,item->type,item->value); return;
        }
    }
}
Value ReadStructField(const Ctx& c,const StructValue& value,const std::string& field,const std::string& type) {
    validate(c,value.type,value.fields);
    for(const auto& entry:definition(c,"structs",value.type.substr(7)).at("fields")) if(entry.at("name")==field) {
        check(entry.at("type")==type,"Struct field type mismatch: "+field);
        return CheckedValueFromJson(c,type,value.fields.at(field));
    }
    throw std::runtime_error("Unknown Struct field: "+field);
}
Value GetUserVariable(Ctx& c,const std::string& type,const std::string& scope,EntityRef owner,const std::string& name) {
    const auto& value=scope.empty() ? GetVariableValue(c,name) : GetScopedVariableValue(c,scope,name,owner);
    const auto packed=VariableJson(value);
    check(packed.is_object() && packed.at("type")==type,"Variable type mismatch: "+name);
    return CheckedValueFromJson(c,type,packed.at("value"));
}
void SetUserVariable(Ctx& c,const std::string& type,const std::string& scope,EntityRef owner,const std::string& name,Value value) {
    const auto packed=VariableJson(value);
    check(packed.is_object() && packed.at("type")==type,"Variable type mismatch: "+name);
    auto checked=CheckedValueFromJson(c,type,packed.at("value"));
    if(scope.empty()) SetVariableValue(c,name,std::move(checked));
    else SetScopedVariableValue(c,scope,name,std::move(checked),owner);
}
Value DispatchUserVariable(Ctx& c,int node,const std::vector<Value>& args) {
    if(node<0) return DispatchUserCollection(c,node,args);
    int index=0,role=-1; std::string type;
    for(const auto& group:std::array<std::string,2>{"structs","enums"}) for(const auto& entry:c.user_types.at(group)) {
        const auto base=entry.value("variable_id",800000+index++*16);
        if(node>=base && node<base+8) {
            role=node-base; type=(group=="structs" ? "struct:" : "enum:")+entry.at("name").get<std::string>();
        }
    }
    if(role<0) return DispatchComponent(c,node,args);
    const std::string scope=std::array<std::string,4>{"","global","scene","entity"}.at(role/2);
    const bool write=role%2!=0;
    const std::size_t offset=scope=="entity" ? 1 : 0;
    check(args.size()==offset+1+(write ? 1 : 0),"User variable argument count mismatch");
    const EntityRef owner=offset ? std::get<EntityRef>(args.at(0)) : EntityRef{};
    const auto name=std::get<std::string>(args.at(offset));
    if(!write) return GetUserVariable(c,type,scope,owner,name);
    SetUserVariable(c,type,scope,owner,name,args.at(offset+1));
    return 0.0;
}

Value DispatchUserCollection(Ctx& c,int node,const std::vector<Value>& args) {
    int index=0,slot=-1,group=-1; std::string element;
    for(const auto& category:{std::string("structs"),std::string("enums")}) for(const auto& entry:c.user_types.at(category)) {
        if(entry.contains("variable_id")) check(entry.at("variable_id").is_number_integer(),"Invalid nominal variable identity");
        const auto variable=entry.value("variable_id",std::int64_t{800000+index++*16});
        check(variable>=800000 && variable<900000 && (variable-800000)%16==0,"Invalid nominal variable identity");
        const auto relative=-(variable*128+1)-node;
        if(relative>=0 && relative<96) {
            slot=relative%32; group=relative/32;
            element=(category=="structs" ? "struct:" : "enum:")+entry.at("name").get<std::string>();
        }
    }
    check(slot>=0,"Unknown user collection node");
    const auto kind=std::array<std::string,3>{"array","map","set"}.at(group);
    const auto type=kind+"<"+element+">";
    if(slot<8) {
        const auto scope=std::array<std::string,4>{"","global","scene","entity"}.at(slot/2);
        const std::size_t offset=scope=="entity" ? 1 : 0;
        const bool write=slot%2!=0;
        check(args.size()==offset+1+(write ? 1 : 0),"Collection variable argument count mismatch");
        const auto owner=offset ? std::get<EntityRef>(args.at(0)) : EntityRef{};
        const auto name=std::get<std::string>(args.at(offset));
        if(!write) return GetUserVariable(c,type,scope,owner,name);
        SetUserVariable(c,type,scope,owner,name,args.at(offset+1)); return 0.0;
    }
    const std::vector<int> counts=group==0 ? std::vector<int>{1,2,3,2,2,3,1,2,2,1,1,2,3} :
        group==1 ? std::vector<int>{1,2,3,2,2,1,1,1,1} : std::vector<int>{1,2,2,2,1,1};
    check(slot>=8 && static_cast<std::size_t>(slot-8)<counts.size(),"Unsupported user collection operation");
    check(args.size()==static_cast<std::size_t>(counts.at(slot-8)),"Collection operation argument count mismatch");
    ValidateTypedValue(c,type,args.at(0));
    auto result=std::get<UserCollectionValue>(args.at(0)).items;
    auto integer=[&](std::size_t i) { return std::get<std::int64_t>(args.at(i)); };
    auto item=[&](std::size_t i) {
        ValidateTypedValue(c,element,args.at(i));
        return std::visit([](const auto& value) { return ToJson(value); },args.at(i));
    };
    auto key=[&](std::size_t i) { auto value=std::get<std::string>(args.at(i)); CheckValue(value); return value; };
    if(group==0) {
        switch(slot) {
        case 8: break;
        case 9: result.push_back(item(1)); break;
        case 10: {const auto at=ArrayIndex(integer(1),result.size(),true); auto& values=result.get_ref<Json::array_t&>(); values.insert(values.begin()+at,item(2)); break;}
        case 11: result.erase(result.begin()+ArrayIndex(integer(1),result.size())); break;
        case 12: return CheckedValueFromJson(c,element,result.at(ArrayIndex(integer(1),result.size())));
        case 13: result.at(ArrayIndex(integer(1),result.size()))=item(2); break;
        case 14: return static_cast<std::int64_t>(result.size());
        case 15: case 16: {
            const auto expected=item(1); auto found=std::find(result.begin(),result.end(),expected);
            if(slot==15) return found!=result.end();
            return found==result.end() ? std::int64_t{-1} : static_cast<std::int64_t>(found-result.begin());
        }
        case 17: std::reverse(result.begin(),result.end()); break;
        case 18: result=Json::array(); break;
        case 19: {
            ValidateTypedValue(c,type,args.at(1)); const auto& right=std::get<UserCollectionValue>(args.at(1)).items;
            CollectionSize(result.size()+right.size()); for(const auto& value:right) result.push_back(value); break;
        }
        case 20: {
            const auto start=integer(1),end=integer(2);
            check(start>=0 && end>=start && static_cast<std::uint64_t>(end)<=result.size(),"Array slice range out of bounds");
            result=Json(Json::array_t(result.begin()+start,result.begin()+end)); break;
        }
        }
    } else if(group==1) {
        switch(slot) {
        case 8: break;
        case 9: { const auto name=key(1); check(result.contains(name),"Missing map key: "+name); return CheckedValueFromJson(c,element,result.at(name)); }
        case 10: result[key(1)]=item(2); break;
        case 11: result.erase(key(1)); break;
        case 12: return result.contains(key(1));
        case 13: { Array<std::string> keys; for(auto it=result.begin();it!=result.end();++it) keys.push_back(it.key()); return keys; }
        case 14: { auto values=Json::array(); for(const auto& value:result) values.push_back(value); return CheckedValueFromJson(c,"array<"+element+">",values); }
        case 15: return static_cast<std::int64_t>(result.size());
        case 16: result=Json::object(); break;
        }
    } else {
        switch(slot) {
        case 8: {auto unique=Json::array(); for(const auto& value:result) if(std::find(unique.begin(),unique.end(),value)==unique.end()) unique.push_back(value); result=std::move(unique); break;}
        case 9: {auto value=item(1); if(std::find(result.begin(),result.end(),value)==result.end()) result.push_back(value); break;}
        case 10: {auto value=item(1); auto it=std::find(result.begin(),result.end(),value); if(it!=result.end()) result.erase(it); break;}
        case 11: {auto value=item(1); return std::find(result.begin(),result.end(),value)!=result.end();}
        case 12: return static_cast<std::int64_t>(result.size());
        case 13: result=Json::array(); break;
        }
    }
    return CheckedValueFromJson(c,type,result);
}

UserCollectionValue ApplyUserArrayCallback(Ctx& c,const std::string& mode,const UserCollectionValue& source,
    const std::function<Value(const Value&)>& invoke) {
    ValidateTypedValue(c,source.type,source);
    check(source.type.starts_with("array<"),"Collection callback requires an array");
    const auto element=source.type.substr(6,source.type.size()-7);
    auto items=IterationValues(source);
    if(mode=="SortArray") std::stable_sort(items.begin(),items.end(),[&](const Value& left,const Value& right) {
        return std::get<double>(invoke(left))<std::get<double>(invoke(right));
    });
    check(mode=="SortArray" || mode=="FilterArray" || mode=="MapArray","Unknown collection callback mode");
    auto result=Json::array();
    for(const auto& value:items) {
        if(mode=="FilterArray" && !std::get<bool>(invoke(value))) continue;
        const auto mapped=mode=="MapArray" ? invoke(value) : value;
        ValidateTypedValue(c,element,mapped);
        result.push_back(std::visit([](const auto& item) { return ToJson(item); },mapped));
    }
    return std::get<UserCollectionValue>(CheckedValueFromJson(c,source.type,result));
}
}
