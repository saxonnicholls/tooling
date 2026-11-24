//
//  version.hpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
/// \file
/// \brief The fixture's version.

// Two copies of the library in one translation unit share this header's guard, so the guard alone would skip the
// second quietly: this check stands before it, with the version written out again (check_version.py compares them).
#if defined(SNICHOLLS_FIXTURE_VERSION_MAJOR) && \
    (SNICHOLLS_FIXTURE_VERSION_MAJOR != 1 || SNICHOLLS_FIXTURE_VERSION_MINOR != 2 || SNICHOLLS_FIXTURE_VERSION_PATCH != 3)
#error "snicholls-fixture: two versions in one translation unit: 1.2.3 here, and another already included"
#endif

#ifndef snicholls_fixture_version_hpp
/// \cond
#define snicholls_fixture_version_hpp   // the guard: Doxygen does not take it for one after the check above
/// \endcond

// #define SNICHOLLS_FIXTURE_VERSION_MAJOR 9 (a comment, not the version)

/// \brief Major version.
#define SNICHOLLS_FIXTURE_VERSION_MAJOR 1
/// \brief Minor version.
#define SNICHOLLS_FIXTURE_VERSION_MINOR 2
/// \brief Patch version.
#define SNICHOLLS_FIXTURE_VERSION_PATCH 3

#endif
