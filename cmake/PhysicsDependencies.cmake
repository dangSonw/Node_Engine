# Keep simulation options identical for Preview, generated games and probes.
function(node_engine_physics_dependencies)
  if(TARGET node_physics)
    return()
  endif()
  set(jolt "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../deps/JoltPhysics-5.6.0")
  if(NOT EXISTS "${jolt}/Jolt/Jolt.h")
    message(FATAL_ERROR "Jolt 5.6.0 is missing. Run tools/fetch_jolt.py first.")
  endif()
  set(DOUBLE_PRECISION ON)
  set(CROSS_PLATFORM_DETERMINISTIC ON)
  set(CPP_EXCEPTIONS_ENABLED ON)
  set(CPP_RTTI_ENABLED ON)
  foreach(option JPH_BUILD_SHARED_LIBS INTERPROCEDURAL_OPTIMIZATION OVERRIDE_CXX_FLAGS
      GENERATE_DEBUG_SYMBOLS ENABLE_ALL_WARNINGS ENABLE_INSTALL ENABLE_OBJECT_STREAM
      DEBUG_RENDERER_IN_DEBUG_AND_RELEASE DEBUG_RENDERER_IN_DISTRIBUTION
      PROFILER_IN_DEBUG_AND_RELEASE PROFILER_IN_DISTRIBUTION
      JPH_USE_DX12 JPH_USE_VK JPH_USE_MTL JPH_USE_CPU_COMPUTE
      TARGET_UNIT_TESTS TARGET_HELLO_WORLD TARGET_PERFORMANCE_TEST TARGET_SAMPLES TARGET_VIEWER
      USE_SSE4_1 USE_SSE4_2 USE_AVX USE_AVX2 USE_AVX512 USE_LZCNT USE_TZCNT USE_F16C USE_FMADD)
    set(${option} OFF)
  endforeach()
  add_subdirectory("${jolt}/Build" "${CMAKE_CURRENT_BINARY_DIR}/_physics/jolt" EXCLUDE_FROM_ALL)
  add_library(node_physics STATIC "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../runtime/src/physics_world.cpp")
  target_include_directories(node_physics PUBLIC "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../runtime/include"
    "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../deps/include" "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../deps/glm-1.0.1")
  target_link_libraries(node_physics PRIVATE Jolt)
  if(MSVC)
    target_compile_options(node_physics PRIVATE /utf-8 /W4)
  else()
    target_compile_options(node_physics PRIVATE -Wall -Wextra -Wpedantic -ffp-contract=off)
  endif()
  if(MINGW)
    target_link_options(node_physics INTERFACE -static)
  endif()
  add_custom_target(node_physics_assets
    COMMAND ${CMAKE_COMMAND} -E make_directory "${CMAKE_CURRENT_BINARY_DIR}/licenses"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different "${jolt}/LICENSE" "${CMAKE_CURRENT_BINARY_DIR}/licenses/Jolt.txt")
  add_dependencies(node_physics node_physics_assets)
endfunction()
