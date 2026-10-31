#pragma once
#include <glm/glm.hpp>
#include <glm/mat4x4.hpp>
#include <glm/gtc/quaternion.hpp>
#include <nlohmann/json.hpp>
#include <cmath>
#include <cstdint>
#include <deque>
#include <initializer_list>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <variant>
#include <vector>

namespace rt {
using Json = nlohmann::json;
using Vec2 = glm::dvec2;
using Vec3 = glm::dvec3;
using Vec4 = glm::dvec4;
using Quat = glm::dquat;
using Mat4 = glm::dmat4;
struct EntityRef { std::string id; bool operator==(const EntityRef&) const = default; };
struct StructValue { std::string type; Json fields; bool operator==(const StructValue&) const = default; };
struct EnumValue { std::string type; std::string value; bool operator==(const EnumValue&) const = default; };
struct UserCollectionValue { std::string type; Json items; bool operator==(const UserCollectionValue&) const = default; };
template<class T> using Array = std::vector<T>;
template<class T> using Map = std::map<std::string, T>;
template<class T> bool ValueEqual(const T& a, const T& b) {
    if constexpr (std::is_same_v<T,Vec2>) return a.x==b.x && a.y==b.y;
    else if constexpr (std::is_same_v<T,Vec3>) return a.x==b.x && a.y==b.y && a.z==b.z;
    else if constexpr (std::is_same_v<T,Vec4>) return a.x==b.x && a.y==b.y && a.z==b.z && a.w==b.w;
    else if constexpr (std::is_same_v<T,Quat>) return a.w==b.w && a.x==b.x && a.y==b.y && a.z==b.z;
    else if constexpr (std::is_same_v<T,Mat4>) {
        for(int column=0;column<4;++column) for(int row=0;row<4;++row)
            if(a[column][row]!=b[column][row]) return false;
        return true;
    } else return a==b;
}
template<class T> struct Set {
    using value_type = T;
    // deque avoids std::vector<bool>'s proxy references while preserving deterministic insertion order.
    std::deque<T> values;
    Set() = default;
    Set(std::initializer_list<T> items) { for(const auto& item:items) if(!contains(item)) values.push_back(item); }
    auto begin() const { return values.begin(); }
    auto end() const { return values.end(); }
    std::size_t size() const { return values.size(); }
    bool contains(const T& item) const {
        for(const auto& value:values) if(ValueEqual(value,item)) return true;
        return false;
    }
    bool operator==(const Set& other) const {
        if(values.size()!=other.values.size()) return false;
        for(std::size_t i=0;i<values.size();++i) if(!ValueEqual(values[i],other.values[i])) return false;
        return true;
    }
};
using Value = std::variant<double, std::int64_t, bool, std::string, Vec2, Vec3, Vec4, Quat, Mat4, EntityRef, StructValue, EnumValue, UserCollectionValue,
    Array<double>, Array<std::int64_t>, Array<bool>, Array<std::string>, Array<Vec2>, Array<Vec3>, Array<Vec4>, Array<Quat>, Array<Mat4>, Array<EntityRef>,
    Map<double>, Map<std::int64_t>, Map<bool>, Map<std::string>, Map<Vec2>, Map<Vec3>, Map<Vec4>, Map<Quat>, Map<Mat4>, Map<EntityRef>,
    Set<double>, Set<std::int64_t>, Set<bool>, Set<std::string>, Set<Vec2>, Set<Vec3>, Set<Vec4>, Set<Quat>, Set<Mat4>, Set<EntityRef>>;
inline constexpr std::size_t MaxCollection = 65536, MaxString = 1048576;
inline double finite(double x) {
    if (!std::isfinite(x)) throw std::runtime_error("Non-finite numeric result");
    return x;
}
inline Vec2 finite(Vec2 v) { return {finite(v.x), finite(v.y)}; }
inline Vec3 finite(Vec3 v) { return {finite(v.x), finite(v.y), finite(v.z)}; }
inline Vec4 finite(Vec4 v) { return {finite(v.x), finite(v.y), finite(v.z), finite(v.w)}; }
inline Quat finite(Quat v) { return {finite(v.w), finite(v.x), finite(v.y), finite(v.z)}; }
inline Mat4 finite(Mat4 v) {
    for(int column=0; column<4; ++column) for(int row=0; row<4; ++row) v[column][row]=finite(v[column][row]);
    return v;
}
template<class T> struct ArrayType : std::false_type {};
template<class T> struct ArrayType<Array<T>> : std::true_type { using Element = T; };
template<class T> struct MapType : std::false_type {};
template<class T> struct MapType<Map<T>> : std::true_type { using Element = T; };
template<class T> struct SetType : std::false_type {};
template<class T> struct SetType<Set<T>> : std::true_type { using Element = T; };

template<class T> std::string TypeName() {
    if constexpr (std::is_same_v<T,double>) return "float";
    else if constexpr (std::is_same_v<T,std::int64_t>) return "int";
    else if constexpr (std::is_same_v<T,bool>) return "bool";
    else if constexpr (std::is_same_v<T,std::string>) return "string";
    else if constexpr (std::is_same_v<T,Vec2>) return "vec2";
    else if constexpr (std::is_same_v<T,Vec3>) return "vec3";
    else if constexpr (std::is_same_v<T,Vec4>) return "vec4";
    else if constexpr (std::is_same_v<T,Quat>) return "quat";
    else if constexpr (std::is_same_v<T,Mat4>) return "mat4";
    else if constexpr (std::is_same_v<T,EntityRef>) return "entity";
    else if constexpr (std::is_same_v<T,StructValue>) return "struct";
    else if constexpr (std::is_same_v<T,EnumValue>) return "enum";
    else if constexpr (std::is_same_v<T,UserCollectionValue>) return "user_collection";
    else if constexpr (ArrayType<T>::value) return "array<"+TypeName<typename ArrayType<T>::Element>()+">";
    else if constexpr (MapType<T>::value) return "map<"+TypeName<typename MapType<T>::Element>()+">";
    else if constexpr (SetType<T>::value) return "set<"+TypeName<typename SetType<T>::Element>()+">";
}
inline void CollectionSize(std::size_t size) {
    if(size > MaxCollection) throw std::runtime_error("Collection exceeds 65536 items");
}
inline void StringSize(std::size_t size) {
    if(size > MaxString) throw std::runtime_error("String exceeds 1048576 UTF-8 bytes");
}
template<class T> void CheckValue(const T& value) {
    if constexpr (std::is_same_v<T,double> || std::is_same_v<T,Vec2> || std::is_same_v<T,Vec3> || std::is_same_v<T,Vec4> || std::is_same_v<T,Quat> || std::is_same_v<T,Mat4>) finite(value);
    else if constexpr (std::is_same_v<T,std::string>) StringSize(value.size());
    else if constexpr (std::is_same_v<T,EntityRef>) StringSize(value.id.size());
    else if constexpr (std::is_same_v<T,UserCollectionValue>) {
        if(value.type.starts_with("map<") ? !value.items.is_object() : !value.items.is_array()) throw std::runtime_error("Invalid typed collection shape");
        CollectionSize(value.items.size());
    }
    else if constexpr (ArrayType<T>::value) {
        CollectionSize(value.size());
        for(const auto& item:value) CheckValue<typename T::value_type>(item);
    } else if constexpr (MapType<T>::value) {
        CollectionSize(value.size());
        for(const auto& [key,item]:value) { CheckValue(key); CheckValue(item); }
    } else if constexpr (SetType<T>::value) {
        CollectionSize(value.size());
        for(const auto& item:value) CheckValue<typename T::value_type>(item);
    }
}
template<class T> T FromJson(const Json& value) {
    if constexpr (std::is_same_v<T,double>) {
        if(!value.is_number()) throw std::runtime_error("Expected float");
        return finite(value.get<double>());
    } else if constexpr (std::is_same_v<T,std::int64_t>) {
        if(!value.is_number_integer() || (value.is_number_unsigned() && value.get<std::uint64_t>() > std::uint64_t(INT64_MAX)))
            throw std::runtime_error("Expected signed 64-bit integer");
        return value.get<T>();
    } else if constexpr (std::is_same_v<T,bool>) return value.get<bool>();
    else if constexpr (std::is_same_v<T,std::string>) {
        auto result=value.get<std::string>(); CheckValue(result); return result;
    } else if constexpr (std::is_same_v<T,EntityRef>) return {FromJson<std::string>(value)};
    else if constexpr (std::is_same_v<T,StructValue>) {
        if(!value.is_object()) throw std::runtime_error("Expected struct object");
        return {"struct", value};
    } else if constexpr (std::is_same_v<T,EnumValue>) {
        return {"enum", FromJson<std::string>(value)};
    }
    else if constexpr (std::is_same_v<T,Vec2> || std::is_same_v<T,Vec3> || std::is_same_v<T,Vec4>) {
        constexpr std::size_t size = std::is_same_v<T,Vec2> ? 2 : std::is_same_v<T,Vec3> ? 3 : 4;
        if(!value.is_array() || value.size()!=size) throw std::runtime_error("Expected "+TypeName<T>()+" array");
        T result{};
        for(std::size_t i=0; i<size; ++i) result[i]=FromJson<double>(value.at(i));
        return result;
    } else if constexpr (std::is_same_v<T,Quat>) {
        if(!value.is_array() || value.size()!=4) throw std::runtime_error("Expected quat array [x,y,z,w]");
        return Quat{FromJson<double>(value.at(3)), FromJson<double>(value.at(0)),
                    FromJson<double>(value.at(1)), FromJson<double>(value.at(2))};
    } else if constexpr (std::is_same_v<T,Mat4>) {
        if(!value.is_array() || value.size()!=16) throw std::runtime_error("Expected mat4 array in column-major order");
        Mat4 result(0.0);
        for(std::size_t i=0; i<16; ++i) result[static_cast<int>(i/4)][static_cast<int>(i%4)]=FromJson<double>(value.at(i));
        return result;
    } else if constexpr (ArrayType<T>::value) {
        if(!value.is_array()) throw std::runtime_error("Expected "+TypeName<T>());
        CollectionSize(value.size()); T result; result.reserve(value.size());
        for(const auto& item:value) result.push_back(FromJson<typename T::value_type>(item));
        return result;
    } else if constexpr (MapType<T>::value) {
        if(!value.is_object()) throw std::runtime_error("Expected "+TypeName<T>());
        CollectionSize(value.size()); T result;
        for(const auto& [key,item]:value.items()) { CheckValue(key); result.emplace(key,FromJson<typename T::mapped_type>(item)); }
        return result;
    } else if constexpr (SetType<T>::value) {
        if(!value.is_array()) throw std::runtime_error("Expected "+TypeName<T>());
        CollectionSize(value.size()); T result;
        for(const auto& item:value) {
            auto parsed=FromJson<typename T::value_type>(item);
            if(result.contains(parsed)) throw std::runtime_error("Set contains duplicate items");
            result.values.push_back(std::move(parsed));
        }
        return result;
    }
}
template<class T> Json ToJson(const T& value) {
    if constexpr (std::is_same_v<T,Vec2>) return Json::array({value.x,value.y});
    else if constexpr (std::is_same_v<T,Vec3>) return Json::array({value.x,value.y,value.z});
    else if constexpr (std::is_same_v<T,Vec4>) return Json::array({value.x,value.y,value.z,value.w});
    else if constexpr (std::is_same_v<T,Quat>) return Json::array({value.x,value.y,value.z,value.w});
    else if constexpr (std::is_same_v<T,Mat4>) {
        auto result=Json::array();
        for(int column=0; column<4; ++column) for(int row=0; row<4; ++row) result.push_back(value[column][row]);
        return result;
    }
    else if constexpr (std::is_same_v<T,EntityRef>) return value.id;
    else if constexpr (std::is_same_v<T,StructValue>) return value.fields;
    else if constexpr (std::is_same_v<T,EnumValue>) return value.value;
    else if constexpr (std::is_same_v<T,UserCollectionValue>) return value.items;
    else if constexpr (ArrayType<T>::value) {
        auto result=Json::array();
        for(const auto& item:value) result.push_back(ToJson<typename T::value_type>(item));
        return result;
    } else if constexpr (MapType<T>::value) {
        auto result=Json::object();
        for(const auto& [key,item]:value) result[key]=ToJson(item);
        return result;
    } else if constexpr (SetType<T>::value) {
        auto result=Json::array();
        for(const auto& item:value) result.push_back(ToJson(item));
        return result;
    } else return value;
}
Value ValueFromJson(const std::string& type, const Json& value);
std::string ValueType(const Value& value);
Json VariableJson(const Value& value);
Array<Value> IterationValues(const Value& value);
Array<std::string> IterationKeys(const Value& value);
inline Vec3 vec_from_json(const Json& value) { return FromJson<Vec3>(value); }
inline Json vec_json(Vec3 value) { return ToJson(value); }
template<class T> T StructGet(const StructValue& value, const std::string& field) {
    if(!value.fields.is_object() || !value.fields.contains(field)) throw std::runtime_error("Struct field is missing: "+field);
    return FromJson<T>(value.fields.at(field));
}
}
