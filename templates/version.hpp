//
//  version.hpp
//  snicholls-example
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//

/// \file
/// \brief Which version of snicholls-example you are compiling against.
/// \ingroup example
///
/// The template of a library's version header (tooling's README, "The version header"): copy it to
/// `<include_root>/version.hpp`, rename EXAMPLE and example, and set the number. The number here,
/// `project(... VERSION)` in CMakeLists.txt and the release tag are checked against each other by `check_version.py`,
/// and so are the literals in the two-versions check below.

// The two-versions check. Two copies of the library in one translation unit share this header's guard, so the guard
// alone would skip the second without a word. This block stands before the guard and stops the compile instead. The
// macros are defined inside the guard, so the version is written out here again; a bump changes both.
#if defined(SNICHOLLS_EXAMPLE_VERSION_MAJOR) && \
    (SNICHOLLS_EXAMPLE_VERSION_MAJOR != 0 || SNICHOLLS_EXAMPLE_VERSION_MINOR != 1 || SNICHOLLS_EXAMPLE_VERSION_PATCH != 0)
#error "snicholls-example: two versions in one translation unit: 0.1.0 here, and another already included"
#endif

#ifndef snicholls_example_version_hpp
/// \cond
#define snicholls_example_version_hpp   // the guard: Doxygen does not take it for one after the check above
/// \endcond

/// \brief Major version of snicholls-example.
#define SNICHOLLS_EXAMPLE_VERSION_MAJOR 0
/// \brief Minor version of snicholls-example.
#define SNICHOLLS_EXAMPLE_VERSION_MINOR 1
/// \brief Patch version of snicholls-example.
#define SNICHOLLS_EXAMPLE_VERSION_PATCH 0

#endif
