#include "runtime.hpp"
#include <RmlUi_Platform_SDL.h>
#include <regex>

namespace rt {
namespace {
void check(bool ok,const std::string& text) { if(!ok) throw std::runtime_error(text); }
bool identifier(const std::string& id,size_t limit=128) {
    return !id.empty() && id.size()<=limit && id.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")==std::string::npos;
}
std::string utf8(const std::filesystem::path& path) { auto s=path.generic_u8string(); return std::string(s.begin(),s.end()); }
struct Listener { std::string node,kind,widget,element; UiHandler callback; };
}
struct UiSystem {
    Json assets;
    std::map<std::string,std::string> templates,instances;
    std::vector<Listener> listeners;
    std::unique_ptr<UiSession> session;
    std::string source;
    bool prepared=false,draining=false;
    int width=960,height=640;
    float density=1;
};
static UiSystem& system(const Ctx& c) { check(bool(c.ui),"UI scene is not initialized"); return *c.ui; }
static UiSession& session(const Ctx& c) { auto& s=system(c); check(bool(s.session),"Scene has no prepared UI templates"); return *s.session; }
std::shared_ptr<UiSystem> CreateUiSystem(const Json& assets) {
    check(assets.is_array() && assets.size()<=128,"At most 128 UI templates are allowed");
    auto next=std::make_shared<UiSystem>(); size_t bytes=0;
    for(const auto& a:assets) {
        check(a.is_object() && a.size()==5 && a.at("version").is_number_integer() && a.at("version")==1 && a.at("type")=="ui","Invalid UI template fields/version");
        const auto id=a.at("id").get<std::string>(),name=a.at("name").get<std::string>(),rml=a.at("rml").get<std::string>();
        check(identifier(id,48) && !next->templates.contains(id),"Invalid or duplicate UI template ID");
        check(!name.empty() && name.size()<=512 && name.find_first_not_of(" \t\r\n")!=std::string::npos &&
              std::none_of(name.begin(),name.end(),[](unsigned char c){return c<32 || c==127;}),"Invalid UI template name");
        bytes+=rml.size();
        check(!rml.empty() && rml.size()<=1024*1024 && rml.find('\0')==std::string::npos && bytes<=8*1024*1024,"UI RML exceeds 1 MiB per template / 8 MiB per scene, or contains NUL");
        next->templates.emplace(id,rml);
    }
    next->assets=assets; return next;
}
Json UiAssets(const Ctx& c) { return c.ui ? c.ui->assets : Json::array(); }
Json UiSnapshot(const Ctx& c) {
    if(!c.ui || c.ui->assets.empty()) return nullptr;
    return {{"instances",c.ui->instances},{"widgets",c.ui->session ? c.ui->session->snapshot() : Json::object()}};
}
static Json bindings(const UiSystem& s) {
    auto result=Json::array();
    for(const auto& listener:s.listeners) result.push_back({{"node",listener.node},{"kind",listener.kind},
        {"widget",listener.widget},{"element",listener.element}});
    return result;
}
Json UiCheckpoint(const Ctx& c) {
    const auto& s=system(c);
    check(s.prepared && !s.draining,"UI checkpoint requires prepared UI outside event dispatch");
    return {{"version",1},{"assets",s.assets},{"bindings",bindings(s)},{"instances",s.instances},
        {"session",s.session ? s.session->checkpoint() : Json(nullptr)}};
}
void RestoreUiCheckpoint(Ctx& target,const Ctx& program,const Json& data,const std::filesystem::path& root,
                         Rml::RenderInterface* renderer,SDL_Window* window,bool defer_platform) {
    const auto original=program.ui; check(bool(original) && !original->draining && (!target.ui || !target.ui->draining),
        "UI restoration is not allowed during event dispatch");
    check(data.is_object() && data.size()==5 && data.at("version").is_number_integer() && data.at("version")==1,
        "Invalid UI checkpoint version/fields");
    check(data.at("assets")==original->assets && data.at("bindings")==bindings(*original),"UI checkpoint templates or event bindings do not match this program");
    const auto& instances=data.at("instances"); check(instances.is_object() && instances.size()<=128,"Invalid UI checkpoint instances");
    Ctx staging; staging.time=target.time; staging.ui=CreateUiSystem(original->assets);
    staging.ui->listeners=original->listeners;
    PrepareUi(staging,root,renderer,window,false);
    for(const auto& [name,asset]:instances.items()) CreateWidget(staging,asset.get<std::string>(),name);
    if(staging.ui->session) {
        staging.ui->session->restore_checkpoint(data.at("session"));
        staging.ui->width=data.at("session").at("dimensions").at(0).get<int>();
        staging.ui->height=data.at("session").at("dimensions").at(1).get<int>();
        staging.ui->density=data.at("session").at("density").get<float>();
    } else check(data.at("session").is_null(),"Unexpected checkpoint session without UI templates");
    SuspendUiPlatform(target); target.ui=std::move(staging.ui);
    if(!defer_platform) ActivateUiPlatform(target);
}
void SuspendUiPlatform(Ctx& c) noexcept { if(c.ui && c.ui->session) c.ui->session->suspend_platform(); }
void ActivateUiPlatform(Ctx& c) noexcept { if(c.ui && c.ui->session) c.ui->session->activate_platform(); }
void PrepareUi(Ctx& c,const std::filesystem::path& root,Rml::RenderInterface* renderer,SDL_Window* window,bool platform_active) {
    auto& s=system(c); check(!s.prepared,"UI is already prepared");
    if(s.assets.empty()) { s.prepared=true; return; }
    const auto project=std::filesystem::canonical(root);
    const auto font=std::filesystem::u8path(SDL_GetBasePath())/"fonts/RobotoMono-Regular.ttf";
    s.source=utf8(project/"inline-ui.rml");
    // Preflight every template with the real parser, layout, image decoder and
    // font engine before committing the replacement scene or GPU resources.
    UiSession validation(font,nullptr,nullptr,project/"assets");
    for(const auto& [id,rml]:s.templates) {
        validation.load("validate",rml,s.source); validation.render(); validation.destroy("validate");
    }
    s.session=std::make_unique<UiSession>(font,renderer,window,project/"assets",platform_active); s.prepared=true;
}
void UpdateUi(Ctx& c,int width,int height,float density) {
    if(c.ui && c.ui->session) { c.ui->width=width; c.ui->height=height; c.ui->density=density; c.ui->session->update(c.time,width,height,density); }
}
static void layout(Ctx& c) { auto& s=system(c); if(s.session) s.session->update(c.time,s.width,s.height,s.density); }
void RenderUi(Ctx& c) { if(c.ui && c.ui->session) c.ui->session->render(); }
bool ProcessUiInput(Ctx& c,SDL_Event& event) { return !c.ui || !c.ui->session || c.ui->session->process(event); }
void ClearUiInput(Ctx& c) { if(c.ui && c.ui->session) c.ui->session->clear_input(); }
void BindUiEvent(Ctx& c,std::string node,std::string kind,std::string widget,std::string element,UiHandler handler) {
    check((kind=="click" || kind=="change" || kind=="submit") && (widget.empty() || identifier(widget)) && (element.empty() || identifier(element)),"Invalid UI event listener");
    auto& s=system(c); check(s.listeners.size()<4096,"UI listener limit exceeded");
    s.listeners.push_back({std::move(node),std::move(kind),std::move(widget),std::move(element),std::move(handler)});
}
void DrainUiEvents(Ctx& c) {
    auto& s=system(c); if(!s.session || s.draining) return;
    s.draining=true;
    const auto previous_self=c.self; auto previous_locals=std::move(c.locals); c.locals.clear(); c.self.clear();
    try {
        for(;;) {
            auto pending=s.session->take_events(); if(pending.empty()) break;
            for(const auto& event:pending) {
                for(const auto& listener:s.listeners) {
                    if(!s.session->alive(event)) break;
                    if(listener.kind!=event.type || (!listener.widget.empty() && listener.widget!=event.document) ||
                       (!listener.element.empty() && listener.element!=event.element)) continue;
                    c.locals.clear(); Tick(c,listener.node); listener.callback(c,event); DrainEvents(c); layout(c);
                }
            }
        }
    } catch(...) { c.self=previous_self; c.locals=std::move(previous_locals); s.draining=false; throw; }
    c.self=previous_self; c.locals=std::move(previous_locals); s.draining=false;
}
void CreateWidget(Ctx& c,const std::string& asset,const std::string& widget) {
    auto& s=system(c); const auto found=s.templates.find(asset); check(found!=s.templates.end(),"Unknown UI template: "+asset);
    session(c).load(widget,found->second,s.source); s.instances[widget]=asset; layout(c);
}
void DestroyWidget(Ctx& c,const std::string& widget) { session(c).destroy(widget); system(c).instances.erase(widget); }
bool WidgetExists(Ctx& c,const std::string& widget) { return c.ui && c.ui->session && c.ui->session->contains(widget); }
void ShowWidget(Ctx& c,const std::string& w,bool visible) { session(c).show(w,visible); layout(c); }
void SetWidgetText(Ctx& c,const std::string& w,const std::string& e,const std::string& text) { session(c).set_text(w,e,text); }
std::string GetWidgetText(Ctx& c,const std::string& w,const std::string& e) { return session(c).text(w,e); }
void SetWidgetValue(Ctx& c,const std::string& w,const std::string& e,double value) { session(c).set_value(w,e,value); }
double GetWidgetValue(Ctx& c,const std::string& w,const std::string& e) { return session(c).value(w,e); }
void SetWidgetChecked(Ctx& c,const std::string& w,const std::string& e,bool checked) { session(c).set_checked(w,e,checked); }
bool GetWidgetChecked(Ctx& c,const std::string& w,const std::string& e) { return session(c).checked(w,e); }
void SetWidgetEnabled(Ctx& c,const std::string& w,const std::string& e,bool enabled) { session(c).set_enabled(w,e,enabled); }
bool GetWidgetEnabled(Ctx& c,const std::string& w,const std::string& e) { return session(c).enabled(w,e); }
void SetWidgetFocus(Ctx& c,const std::string& w,const std::string& e) { layout(c); session(c).focus(w,e); }
void SetWidgetStyle(Ctx& c,const std::string& w,const std::string& e,const std::string& p,const std::string& value) { session(c).set_style(w,e,p,value); }
void SetWidgetPosition(Ctx& c,const std::string& w,const std::string& e,double x,double y) {
    check(std::isfinite(x) && std::isfinite(y) && std::abs(x)<=1000000 && std::abs(y)<=1000000,"Invalid UI position");
    auto& ui=session(c); ui.set_style(w,e,"position","absolute"); ui.set_style(w,e,"left",std::to_string(x)+"px"); ui.set_style(w,e,"top",std::to_string(y)+"px");
}
void SetWidgetSize(Ctx& c,const std::string& w,const std::string& e,double width,double height) {
    check(std::isfinite(width) && std::isfinite(height) && width>=0 && height>=0 && width<=1000000 && height<=1000000,"Invalid UI size");
    auto& ui=session(c); ui.set_style(w,e,"width",std::to_string(width)+"px"); ui.set_style(w,e,"height",std::to_string(height)+"px");
}
std::map<unsigned long long,std::vector<Json>> LoadUiReplay(const Json& data) {
    check(data.is_object() && data.size()==2 && data.at("version").is_number_integer() && data.at("version")==1 && data.at("events").is_array() && data.at("events").size()<=100000,"Invalid UI replay/version");
    std::map<unsigned long long,std::vector<Json>> result; unsigned long long previous=0;
    for(const auto& e:data.at("events")) {
        check(e.is_object() && e.at("frame").is_number_unsigned() && e.at("frame")<1000000,"Invalid UI replay frame");
        auto frame=e.at("frame").get<unsigned long long>(); check(frame>=previous,"UI replay frames must be ordered"); previous=frame;
        const auto kind=e.at("type").get<std::string>(); bool valid=false;
        if(kind=="move") valid=e.size()==4 && e.at("x").is_number_integer() && e.at("y").is_number_integer() && std::abs(e.at("x").get<double>())<=1000000 && std::abs(e.at("y").get<double>())<=1000000;
        else if(kind=="button") valid=e.size()==4 && e.at("button").is_number_integer() && e.at("button")>=0 && e.at("button")<=2 && e.at("down").is_boolean();
        else if(kind=="text") valid=e.size()==3 && e.at("text").is_string() && e.at("text").get<std::string>().size()<=65536 && e.at("text").get<std::string>().find('\0')==std::string::npos;
        else if(kind=="key") valid=e.size()==4 && e.at("key").is_string() && RmlSDL::ConvertKey(SDL_GetKeyFromName(e.at("key").get<std::string>().c_str()))!=Rml::Input::KI_UNKNOWN && e.at("down").is_boolean();
        else if(kind=="clear") valid=e.size()==2;
        check(valid,"Invalid UI replay event"); result[frame].push_back(e);
    }
    return result;
}
void AdvanceUiInput(Ctx& c,const std::vector<Json>& events) {
    layout(c);
    for(const auto& e:events) {
        auto& ui=session(c); const auto kind=e.at("type").get<std::string>();
        if(kind=="move") ui.pointer_move(e.at("x"),e.at("y"));
        else if(kind=="button") ui.pointer_button(e.at("button"),e.at("down"));
        else if(kind=="text") ui.text_input(e.at("text"));
        else if(kind=="key") ui.key_input(RmlSDL::ConvertKey(SDL_GetKeyFromName(e.at("key").get<std::string>().c_str())),e.at("down"));
        else ui.clear_input();
        layout(c);
    }
}
}
