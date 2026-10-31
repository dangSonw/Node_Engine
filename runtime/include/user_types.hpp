#pragma once
#include "values.hpp"
#include <functional>

namespace rt {
struct Ctx;
Value CheckedValueFromJson(const Ctx&,const std::string& type,const Json& value);
Value ReadStructField(const Ctx&,const StructValue&,const std::string& field,const std::string& type);
Value GetUserVariable(Ctx&,const std::string& type,const std::string& scope,EntityRef owner,const std::string& name);
void SetUserVariable(Ctx&,const std::string& type,const std::string& scope,EntityRef owner,const std::string& name,Value value);
Value DispatchUserVariable(Ctx&,int node,const std::vector<Value>& args);
void ValidateStoredUserValue(const Ctx&,const Value&);
void ValidateTypedValue(const Ctx&,const std::string& type,const Value&);
Value DispatchUserCollection(Ctx&,int node,const std::vector<Value>&);
UserCollectionValue ApplyUserArrayCallback(Ctx&,const std::string& mode,const UserCollectionValue&,
    const std::function<Value(const Value&)>&);
}
