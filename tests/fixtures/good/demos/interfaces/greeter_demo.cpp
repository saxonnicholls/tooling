//
//  greeter_demo.cpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
#include <snicholls/fixture/interfaces/greeter.hpp>

struct hello { int greet() const { return 2; } };

int main() { return snicholls::greeter_adapter<hello>{hello{}}.greet() == 2 ? 0 : 1; }
