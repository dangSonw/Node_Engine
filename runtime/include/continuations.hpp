#pragma once
#include "values.hpp"
#include <functional>
#include <memory>

namespace rt {
struct Ctx;
struct Continuations;
using CapturedValues = std::map<std::pair<std::string,std::string>,Value>;
using ContinuationEval = std::function<Value(Ctx&,std::size_t,std::size_t)>;
using ContinuationAction = std::function<std::vector<Value>(Ctx&,std::size_t,const std::vector<Value>&)>;
void ConfigureContinuations(Ctx&,const Json&,ContinuationEval={},ContinuationAction={});
void StartContinuation(Ctx&,std::size_t,CapturedValues={});
void AdvanceContinuations(Ctx&);
void ForgetEntityContinuations(Ctx&,const std::string&);
Json ContinuationCheckpoint(const Ctx&);
void RestoreContinuations(Ctx&,const Ctx&,const Json&);
}
