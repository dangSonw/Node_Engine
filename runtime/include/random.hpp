#pragma once
#include "values.hpp"
#include <tuple>
namespace rt {
struct Ctx;
void SetRandomSeed(Ctx&,int64_t);
int64_t GetRandomSeed(Ctx&);
double RandomFloat(Ctx&,double,double);
int64_t RandomInteger(Ctx&,int64_t,int64_t);
bool RandomBoolean(Ctx&,double);
Vec3 RandomVector(Ctx&,Vec3,Vec3);
Vec3 RandomDirection(Ctx&);
int64_t RandomItemIndex(Ctx&,size_t);
int64_t RandomWeightedIndex(Ctx&,size_t,const Array<double>&);
Array<int64_t> RandomShuffleOrder(Ctx&,size_t);
template<class T> std::tuple<T,int64_t> RandomItem(Ctx& c,const Array<T>& items) {
    CheckValue(items); const auto index=RandomItemIndex(c,items.size());
    return {items[index],index};
}
template<class T> std::tuple<T,int64_t> RandomWeightedItem(Ctx& c,const Array<T>& items,const Array<double>& weights) {
    CheckValue(items); const auto index=RandomWeightedIndex(c,items.size(),weights);
    return {items[index],index};
}
template<class T> Array<T> ShuffleArray(Ctx& c,const Array<T>& items) {
    CheckValue(items); auto result=items;
    const auto order=RandomShuffleOrder(c,items.size());
    for(size_t i=0;i<items.size();++i) result[i]=items[order[i]];
    return result;
}
Json RandomCheckpoint(const Ctx&);
void RestoreRandom(Ctx&,const Json&);
}
