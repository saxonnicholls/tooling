//
//  version_demo.cpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
#include <snicholls/fixture/version.hpp>

#include <cstdio>

int main()
{
    std::printf("version %d.%d.%d\n", SNICHOLLS_FIXTURE_VERSION_MAJOR, SNICHOLLS_FIXTURE_VERSION_MINOR,
                SNICHOLLS_FIXTURE_VERSION_PATCH);
    return 0;
}
