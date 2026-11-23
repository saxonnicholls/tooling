//
//  greeter_demo.cpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
#include <snicholls/fixture/concepts/greeter.hpp>

struct hello { int greet() const { return 1; } };

int main() { return snicholls::greeter<hello> ? 0 : 1; }
