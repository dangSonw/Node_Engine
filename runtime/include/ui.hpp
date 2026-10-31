#pragma once
#include "values.hpp"
#include "ui_session.hpp"
#include <functional>
#include <map>

namespace rt {
struct Ctx;
struct UiSystem;
using UiHandler=std::function<void(Ctx&,const UiEvent&)>;
std::shared_ptr<UiSystem> CreateUiSystem(const Json&);
Json UiAssets(const Ctx&);
Json UiSnapshot(const Ctx&);
Json UiCheckpoint(const Ctx&);
void RestoreUiCheckpoint(Ctx& target,const Ctx& bindings,const Json&,
    const std::filesystem::path&,Rml::RenderInterface* renderer=nullptr,SDL_Window* window=nullptr,bool defer_platform=false);
void PrepareUi(Ctx&,const std::filesystem::path&,Rml::RenderInterface* renderer=nullptr,SDL_Window* window=nullptr,bool platform_active=true);
void SuspendUiPlatform(Ctx&) noexcept;
void ActivateUiPlatform(Ctx&) noexcept;
void UpdateUi(Ctx&,int width=960,int height=640,float density=1);
void RenderUi(Ctx&);
bool ProcessUiInput(Ctx&,SDL_Event&);
void ClearUiInput(Ctx&);
void BindUiEvent(Ctx&,std::string node,std::string kind,std::string widget,std::string element,UiHandler);
void DrainUiEvents(Ctx&);
void CreateWidget(Ctx&,const std::string& asset,const std::string& widget);
void DestroyWidget(Ctx&,const std::string& widget);
bool WidgetExists(Ctx&,const std::string& widget);
void ShowWidget(Ctx&,const std::string& widget,bool visible);
void SetWidgetText(Ctx&,const std::string& widget,const std::string& element,const std::string& text);
std::string GetWidgetText(Ctx&,const std::string& widget,const std::string& element);
void SetWidgetValue(Ctx&,const std::string& widget,const std::string& element,double value);
double GetWidgetValue(Ctx&,const std::string& widget,const std::string& element);
void SetWidgetChecked(Ctx&,const std::string& widget,const std::string& element,bool checked);
bool GetWidgetChecked(Ctx&,const std::string& widget,const std::string& element);
void SetWidgetEnabled(Ctx&,const std::string& widget,const std::string& element,bool enabled);
bool GetWidgetEnabled(Ctx&,const std::string& widget,const std::string& element);
void SetWidgetFocus(Ctx&,const std::string& widget,const std::string& element);
void SetWidgetStyle(Ctx&,const std::string& widget,const std::string& element,const std::string& property,const std::string& value);
void SetWidgetPosition(Ctx&,const std::string& widget,const std::string& element,double x,double y);
void SetWidgetSize(Ctx&,const std::string& widget,const std::string& element,double width,double height);
std::map<unsigned long long,std::vector<Json>> LoadUiReplay(const Json&);
void AdvanceUiInput(Ctx&,const std::vector<Json>&);
}
