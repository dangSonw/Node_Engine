#include "values.hpp"
namespace rt {
std::string ValueType(const Value& value) {
    return std::visit([](const auto& item) {
        using T=std::decay_t<decltype(item)>;
        if constexpr(std::is_same_v<T,StructValue> || std::is_same_v<T,EnumValue> || std::is_same_v<T,UserCollectionValue>) return item.type;
        else return TypeName<T>();
    },value);
}
Value ValueFromJson(const std::string& type, const Json& value) {
    for(const std::string kind:{"array","map","set"}) for(const std::string nominal:{"struct:","enum:"})
        if(type.starts_with(kind+"<"+nominal) && type.ends_with(">")) {
            UserCollectionValue result{type,value}; CheckValue(result);
            if(kind=="set") for(std::size_t i=0;i<value.size();++i) for(std::size_t j=0;j<i;++j)
                if(value.at(i)==value.at(j)) throw std::runtime_error("Set contains duplicate elements");
            return result;
        }
    if(type.rfind("struct:", 0)==0) {
        if(!value.is_object()) throw std::runtime_error("Expected "+type);
        return StructValue{type,value};
    }
    if(type.rfind("enum:", 0)==0) {
        if(!value.is_string()) throw std::runtime_error("Expected "+type);
        return EnumValue{type,value.get<std::string>()};
    }
#define PARSE_TYPE(T) \
    if(type==TypeName<T>()) return FromJson<T>(value); \
    if(type==TypeName<Array<T>>()) return FromJson<Array<T>>(value); \
    if(type==TypeName<Map<T>>()) return FromJson<Map<T>>(value); \
    if(type==TypeName<Set<T>>()) return FromJson<Set<T>>(value);
    PARSE_TYPE(double)
    PARSE_TYPE(std::int64_t)
    PARSE_TYPE(bool)
    PARSE_TYPE(std::string)
    PARSE_TYPE(Vec2)
    PARSE_TYPE(Vec3)
    PARSE_TYPE(Vec4)
    PARSE_TYPE(Quat)
    PARSE_TYPE(Mat4)
    PARSE_TYPE(EntityRef)
#undef PARSE_TYPE
    throw std::runtime_error("Unknown value type: "+type);
}
Json VariableJson(const Value& value) {
    return std::visit([](const auto& item)->Json {
        using T=std::decay_t<decltype(item)>;
        if constexpr(std::is_same_v<T,double>) return item; // Version-one compatibility.
        else if constexpr(std::is_same_v<T,StructValue>) return {{"type",item.type},{"value",item.fields}};
        else if constexpr(std::is_same_v<T,EnumValue>) return {{"type",item.type},{"value",item.value}};
        else if constexpr(std::is_same_v<T,UserCollectionValue>) return {{"type",item.type},{"value",item.items}};
        else return {{"type",TypeName<T>()},{"value",ToJson(item)}};
    },value);
}
Array<Value> IterationValues(const Value& value) {
    return std::visit([](const auto& items)->Array<Value> {
        using T=std::decay_t<decltype(items)>;
        if constexpr(std::is_same_v<T,UserCollectionValue>) {
            const auto element=items.type.substr(items.type.find('<')+1,items.type.size()-items.type.find('<')-2);
            Array<Value> result; result.reserve(items.items.size());
            for(const auto& item:items.items) result.push_back(ValueFromJson(element,item));
            return result;
        } else if constexpr(ArrayType<T>::value) {
            Array<Value> result; result.reserve(items.size());
            for(const auto& item:items) result.emplace_back(typename T::value_type(item));
            return result;
        } else if constexpr(SetType<T>::value) {
            Array<Value> result; result.reserve(items.size());
            for(const auto& item:items) result.emplace_back(typename T::value_type(item));
            return result;
        } else if constexpr(MapType<T>::value) {
            Array<Value> result; result.reserve(items.size());
            for(const auto& [key,item]:items) result.emplace_back(typename T::mapped_type(item));
            return result;
        } else throw std::runtime_error("For Each requires an array, set or map");
    },value);
}
Array<std::string> IterationKeys(const Value& value) {
    return std::visit([](const auto& items)->Array<std::string> {
        using T=std::decay_t<decltype(items)>;
        if constexpr(std::is_same_v<T,UserCollectionValue>) {
            Array<std::string> result;
            if(items.items.is_object()) for(auto it=items.items.begin();it!=items.items.end();++it) result.push_back(it.key());
            return result;
        } else if constexpr(MapType<T>::value) {
            Array<std::string> result; result.reserve(items.size());
            for(const auto& [key,item]:items) result.push_back(key);
            return result;
        } else return {};
    },value);
}
}
