#include "runtime.hpp"
#include <bit>
#include <numeric>
#include <numbers>

namespace rt {
namespace {
void check(bool okay,const char* message) { if(!okay) throw std::runtime_error(message); }
// SplitMix64, Sebastiano Vigna (2015), public domain:
// https://prng.di.unimi.it/splitmix64.c
uint64_t draw(uint64_t& state) {
    uint64_t z=(state+=0x9e3779b97f4a7c15ULL);
    z=(z^(z>>30))*0xbf58476d1ce4e5b9ULL;
    z=(z^(z>>27))*0x94d049bb133111ebULL;
    return z^(z>>31);
}
double unit(uint64_t& state) { return double(draw(state)>>11)*0x1.0p-53; }
double floating(uint64_t& state,double low,double high) {
    if(low==high) return low;
    const double value=std::min(std::lerp(low,high,unit(state)),std::nextafter(high,low));
    check(std::isfinite(value) && value>=low && value<high,"Invalid random float result");
    return value;
}
int64_t integer(uint64_t& state,int64_t low,int64_t high) {
    if(low==high) return low;
    const uint64_t span=uint64_t(high)-uint64_t(low)+1;
    const uint64_t threshold=span ? (uint64_t(0)-span)%span : 0;
    for(int attempt=0;attempt<1024;++attempt) {
        const auto value=draw(state);
        if(value>=threshold) return std::bit_cast<int64_t>(uint64_t(low)+(span ? value%span : value));
    }
    throw std::runtime_error("Random Integer exceeded 1024 rejection attempts");
}
}
void SetRandomSeed(Ctx& c,int64_t seed) { c.random_seed=seed; c.random_state=static_cast<uint64_t>(seed); }
int64_t GetRandomSeed(Ctx& c) { return c.random_seed; }
double RandomFloat(Ctx& c,double low,double high) {
    check(std::isfinite(low) && std::isfinite(high) && low<=high,"Random Float requires finite Minimum <= Maximum");
    auto state=c.random_state;
    const double value=floating(state,low,high);
    c.random_state=state; return value;
}
int64_t RandomInteger(Ctx& c,int64_t low,int64_t high) {
    check(low<=high,"Random Integer requires Minimum <= Maximum");
    auto state=c.random_state;
    const auto result=integer(state,low,high); c.random_state=state; return result;
}
bool RandomBoolean(Ctx& c,double probability) {
    check(std::isfinite(probability) && probability>=0 && probability<=1,"Random Boolean Probability must be between 0 and 1");
    if(probability==0 || probability==1) return probability==1;
    return unit(c.random_state)<probability;
}
Vec3 RandomVector(Ctx& c,Vec3 low,Vec3 high) {
    for(int axis=0;axis<3;++axis)
        check(std::isfinite(low[axis]) && std::isfinite(high[axis]) && low[axis]<=high[axis],
              "Random Vector requires finite Minimum <= Maximum on every axis");
    auto state=c.random_state; Vec3 result;
    for(int axis=0;axis<3;++axis) result[axis]=floating(state,low[axis],high[axis]);
    c.random_state=state; return result;
}
Vec3 RandomDirection(Ctx& c) {
    auto state=c.random_state;
    // Uniform height and azimuth give equal probability per surface area.
    const double y=1-2*unit(state), angle=2*std::numbers::pi*unit(state);
    const double radius=std::sqrt(std::max(0.,(1-y)*(1+y)));
    const auto result=finite(Vec3{radius*std::cos(angle),y,radius*std::sin(angle)});
    c.random_state=state; return result;
}
int64_t RandomItemIndex(Ctx& c,size_t count) {
    CollectionSize(count); check(count>0,"Random Item requires a nonempty array");
    return RandomInteger(c,0,static_cast<int64_t>(count)-1);
}
int64_t RandomWeightedIndex(Ctx& c,size_t count,const Array<double>& weights) {
    CollectionSize(count); CheckValue(weights);
    check(count>0 && weights.size()==count,"Random Weighted Item requires matching nonempty arrays");
    double largest=0; size_t positives=0,last=0;
    for(size_t i=0;i<count;++i) {
        check(weights[i]>=0,"Random weights must be nonnegative");
        largest=std::max(largest,weights[i]);
        if(weights[i]>0) { ++positives; last=i; }
    }
    check(positives>0,"Random weights must include a positive value");
    if(positives==1) return static_cast<int64_t>(last);
    // Scaling keeps even DBL_MAX weights within the bounded collection sum.
    double total=0; for(const auto w:weights) total+=w/largest;
    const double chosen=std::min(unit(c.random_state)*total,std::nextafter(total,0.));
    double sum=0;
    for(size_t i=0;i<count;++i) {
        sum+=weights[i]/largest;
        if(weights[i]>0 && chosen<sum) return static_cast<int64_t>(i);
    }
    return static_cast<int64_t>(last);
}
Array<int64_t> RandomShuffleOrder(Ctx& c,size_t count) {
    CollectionSize(count); Array<int64_t> result(count); std::iota(result.begin(),result.end(),0);
    auto state=c.random_state;
    for(size_t i=count;i>1;--i) {
        const auto selected=integer(state,0,static_cast<int64_t>(i)-1);
        std::swap(result[i-1],result[selected]);
    }
    c.random_state=state; return result;
}
Json RandomCheckpoint(const Ctx& c) {
    std::string encoded(16,'0'); auto state=c.random_state;
    for(int i=15;i>=0;--i) { encoded[i]="0123456789abcdef"[state&15]; state>>=4; }
    return {{"algorithm","splitmix64-v1"},{"seed",c.random_seed},{"state",encoded}};
}
void RestoreRandom(Ctx& c,const Json& saved) {
    check(saved.is_object() && saved.size()==3 && saved.value("algorithm",Json())=="splitmix64-v1",
          "Invalid saved random generator");
    const auto seed=FromJson<int64_t>(saved.at("seed"));
    const auto encoded=FromJson<std::string>(saved.at("state"));
    check(encoded.size()==16,"Invalid saved random state length");
    uint64_t state=0;
    for(char digit:encoded) {
        check((digit>='0' && digit<='9') || (digit>='a' && digit<='f'),"Invalid saved random state encoding");
        state=(state<<4)|uint64_t(digit<='9' ? digit-'0' : digit-'a'+10);
    }
    c.random_seed=seed; c.random_state=state;
}
}
