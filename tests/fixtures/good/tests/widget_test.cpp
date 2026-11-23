//
//  widget_test.cpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
#include <snicholls/fixture/widget.hpp>

static_assert(snicholls::widget(2) == 5);

int main(int argc, char**) { return snicholls::widget(argc) == 3 ? 0 : 1; }
