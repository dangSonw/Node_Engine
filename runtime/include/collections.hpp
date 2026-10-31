#pragma once
#include "values.hpp"
#include <algorithm>
#include <iterator>

namespace rt {
inline std::int64_t Integer(std::int64_t value) { return value; }
inline std::int64_t IntegerAdd(std::int64_t a, std::int64_t b) {
    if((b>0 && a>INT64_MAX-b) || (b<0 && a<INT64_MIN-b)) throw std::runtime_error("Integer overflow");
    return a+b;
}
inline std::int64_t IntegerSubtract(std::int64_t a, std::int64_t b) {
    if((b>0 && a<INT64_MIN+b) || (b<0 && a>INT64_MAX+b)) throw std::runtime_error("Integer overflow");
    return a-b;
}
inline std::int64_t IntegerMultiply(std::int64_t a, std::int64_t b) {
    if(a>0 ? (b>0 ? a>INT64_MAX/b : b<INT64_MIN/a) :
       (a<0 && (b>0 ? a<INT64_MIN/b : b<0 && a<INT64_MAX/b)))
        throw std::runtime_error("Integer overflow");
    return a*b;
}
inline bool IntegerLess(std::int64_t a, std::int64_t b) { return a<b; }
inline bool IntegerEqual(std::int64_t a, std::int64_t b) { return a==b; }
inline std::int64_t BitwiseAnd(std::int64_t a, std::int64_t b) { return a & b; }
inline std::int64_t BitwiseOr(std::int64_t a, std::int64_t b) { return a | b; }
inline std::int64_t BitwiseXor(std::int64_t a, std::int64_t b) { return a ^ b; }
inline std::int64_t IntegerDivide(std::int64_t a, std::int64_t b) {
    if (b == 0) throw std::runtime_error("Integer division by zero");
    if (a == INT64_MIN && b == -1) throw std::runtime_error("Integer overflow");
    return a / b;
}
inline std::int64_t IntegerModulo(std::int64_t a, std::int64_t b) {
    if (b == 0) throw std::runtime_error("Integer modulo by zero");
    if (a == INT64_MIN && b == -1) throw std::runtime_error("Integer overflow");
    return a % b;
}
inline std::int64_t IntegerAbs(std::int64_t value) {
    if (value == INT64_MIN) throw std::runtime_error("Integer overflow");
    return value < 0 ? -value : value;
}
inline std::int64_t IntegerMin(std::int64_t a, std::int64_t b) { return std::min(a,b); }
inline std::int64_t IntegerMax(std::int64_t a, std::int64_t b) { return std::max(a,b); }
inline bool IntegerLessEqual(std::int64_t a, std::int64_t b) { return a<=b; }
inline bool IntegerGreaterEqual(std::int64_t a, std::int64_t b) { return a>=b; }
inline bool IntegerNotEqual(std::int64_t a, std::int64_t b) { return a!=b; }
inline double IntegerToFloat(std::int64_t value) { return static_cast<double>(value); }
inline std::int64_t TruncateToInteger(double value) {
    if(!std::isfinite(value) || value < -9223372036854775808.0 || value >= 9223372036854775808.0)
        throw std::runtime_error("Float outside signed 64-bit integer range");
    return static_cast<std::int64_t>(value);
}
inline std::size_t ArrayIndex(std::int64_t index, std::size_t size, bool insertion=false) {
    if(index<0 || std::uint64_t(index)>size || (!insertion && std::uint64_t(index)==size))
        throw std::runtime_error("Array index "+std::to_string(index)+" out of range for size "+std::to_string(size));
    return static_cast<std::size_t>(index);
}
template<class T> Array<T> CreateArray(Array<T> array) { CheckValue(array); return array; }
template<class T> Array<T> ArrayAppend(Array<T> array, T item) {
    CollectionSize(array.size()+1); CheckValue(item); array.push_back(item); return array;
}
template<class T> Array<T> ArrayConcat(Array<T> left, const Array<T>& right) {
    CollectionSize(left.size()+right.size());
    for(const auto& item:right) { CheckValue(item); left.push_back(item); }
    return left;
}
template<class T> Array<T> ArraySlice(const Array<T>& array, std::int64_t start, std::int64_t end) {
    if(start<0 || end<start || std::uint64_t(end)>array.size())
        throw std::runtime_error("Array slice range "+std::to_string(start)+".."+std::to_string(end)+" out of range for size "+std::to_string(array.size()));
    Array<T> result;
    result.reserve(static_cast<std::size_t>(end-start));
    for(std::int64_t index=start; index<end; ++index) result.push_back(array[static_cast<std::size_t>(index)]);
    return result;
}
template<class T> Array<T> ArrayInsert(Array<T> array, std::int64_t index, T item) {
    auto position=ArrayIndex(index,array.size(),true);
    CollectionSize(array.size()+1); CheckValue(item); array.insert(array.begin()+position,item); return array;
}
template<class T> Array<T> ArrayRemoveAt(Array<T> array, std::int64_t index) {
    auto position=ArrayIndex(index,array.size()); array.erase(array.begin()+position); return array;
}
template<class T> T ArrayGet(const Array<T>& array, std::int64_t index) { return array[ArrayIndex(index,array.size())]; }
template<class T> T ArrayGet(const Set<T>& set, std::int64_t index) {
    if(index<0 || std::uint64_t(index)>=set.size())
        throw std::runtime_error("Set index "+std::to_string(index)+" out of range for size "+std::to_string(set.size()));
    return set.values[static_cast<std::size_t>(index)];
}
template<class T> std::string MapKeyAt(const Map<T>& map, std::int64_t index) {
    if(index<0 || std::uint64_t(index)>=map.size())
        throw std::runtime_error("Map index "+std::to_string(index)+" out of range for size "+std::to_string(map.size()));
    auto it=map.begin(); std::advance(it,static_cast<std::size_t>(index)); return it->first;
}
template<class T> T MapValueAt(const Map<T>& map, std::int64_t index) {
    if(index<0 || std::uint64_t(index)>=map.size())
        throw std::runtime_error("Map index "+std::to_string(index)+" out of range for size "+std::to_string(map.size()));
    auto it=map.begin(); std::advance(it,static_cast<std::size_t>(index)); return it->second;
}
template<class T> Array<T> ArraySet(Array<T> array, std::int64_t index, T item) {
    auto position=ArrayIndex(index,array.size()); CheckValue(item); array[position]=item; return array;
}
template<class T> std::int64_t ArrayLength(const Array<T>& array) { return static_cast<std::int64_t>(array.size()); }
template<class T> std::int64_t ArrayLength(const Set<T>& set) { return static_cast<std::int64_t>(set.size()); }
template<class T> std::int64_t ArrayFind(const Array<T>& array, const T& item) {
    const auto found=std::find(array.begin(),array.end(),item);
    return found==array.end() ? -1 : static_cast<std::int64_t>(found-array.begin());
}
template<class T> bool ArrayContains(const Array<T>& array, const T& item) { return ArrayFind(array,item)>=0; }
template<class T> Array<T> ArrayReverse(Array<T> array) { std::reverse(array.begin(),array.end()); return array; }
template<class T> Array<T> ArrayClear(const Array<T>&) { return {}; }
template<class T> Map<T> CreateMap(Map<T> map) { CheckValue(map); return map; }
template<class T> T MapGet(const Map<T>& map, const std::string& key) {
    const auto found=map.find(key);
    if(found==map.end()) throw std::runtime_error("Map key not found: "+key);
    return found->second;
}
template<class T> Map<T> MapSet(Map<T> map, std::string key, T item) {
    if(!map.contains(key)) CollectionSize(map.size()+1);
    CheckValue(key); CheckValue(item); map[std::move(key)]=std::move(item); return map;
}
template<class T> Map<T> MapRemove(Map<T> map, const std::string& key) { map.erase(key); return map; }
template<class T> bool MapHasKey(const Map<T>& map, const std::string& key) { return map.contains(key); }
template<class T> Array<std::string> MapKeys(const Map<T>& map) {
    Array<std::string> keys; keys.reserve(map.size());
    for(const auto& entry:map) keys.push_back(entry.first);
    return keys;
}
template<class T> Array<T> MapValues(const Map<T>& map) {
    Array<T> values; values.reserve(map.size());
    for(const auto& entry:map) values.push_back(entry.second);
    return values;
}
template<class T> std::int64_t MapSize(const Map<T>& map) { return static_cast<std::int64_t>(map.size()); }
template<class T> Map<T> MapClear(const Map<T>&) { return {}; }
template<class T> Set<T> CreateSet(Set<T> set) { CheckValue(set); return set; }
template<class T> Set<T> SetAdd(Set<T> set, T item) {
    CheckValue(item);
    if(!set.contains(item)) { CollectionSize(set.size()+1); set.values.push_back(std::move(item)); }
    return set;
}
template<class T> Set<T> SetRemove(Set<T> set, const T& item) {
    set.values.erase(std::remove_if(set.values.begin(),set.values.end(),[&](const auto& value){ return ValueEqual(value,item); }),set.values.end());
    return set;
}
template<class T> bool SetContains(const Set<T>& set, const T& item) { return set.contains(item); }
template<class T> std::int64_t SetSize(const Set<T>& set) { return static_cast<std::int64_t>(set.size()); }
template<class T> Set<T> SetClear(const Set<T>&) { return {}; }
inline std::string FormatFloat(double value) { return Json(finite(value)).dump(); }
inline std::string FormatInteger(std::int64_t value) { return std::to_string(value); }
inline std::string FormatBoolean(bool value) { return value ? "true" : "false"; }
inline std::string ConcatStrings(std::string a, const std::string& b) { StringSize(a.size()+b.size()); return a+b; }
inline bool StringEqual(const std::string& a, const std::string& b) { return a==b; }
inline Array<std::string> StringSplit(const std::string& text, const std::string& separator) {
    if(separator.empty()) throw std::runtime_error("Split separator cannot be empty");
    Array<std::string> result; std::size_t begin=0;
    for(;;) {
        const auto end=text.find(separator,begin); CollectionSize(result.size()+1);
        result.push_back(text.substr(begin,end==std::string::npos ? end : end-begin));
        if(end==std::string::npos) return result;
        begin=end+separator.size();
    }
}
inline std::string StringReplace(const std::string& text, const std::string& find, const std::string& replacement) {
    if(find.empty()) throw std::runtime_error("Replace search cannot be empty");
    std::string result; std::size_t begin=0;
    for(;;) {
        auto end=text.find(find,begin);
        auto count=(end==std::string::npos ? text.size() : end)-begin;
        StringSize(result.size()+count); result.append(text,begin,count);
        if(end==std::string::npos) return result;
        StringSize(result.size()+replacement.size()); result+=replacement; begin=end+find.size();
    }
}
inline std::string StringJoin(const Array<std::string>& items, const std::string& separator) {
    std::string result;
    for(std::size_t i=0;i<items.size();++i) {
        StringSize(result.size()+items[i].size()+(i ? separator.size() : 0));
        if(i) result+=separator;
        result+=items[i];
    }
    return result;
}
}
