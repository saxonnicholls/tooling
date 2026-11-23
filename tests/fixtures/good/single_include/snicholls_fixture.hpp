//
//  snicholls_fixture.hpp
//
//  GENERATED from <snicholls/fixture/fixture.hpp> by tooling's scripts/single_include.py: never edit by hand.
//  Regenerate with `make single-include`; CI fails while it is stale.
//

//
//  fixture.hpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
/// \file
/// \brief The umbrella header.

#ifndef snicholls_fixture_fixture_hpp
#define snicholls_fixture_fixture_hpp

//
//  greeter.hpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
/// \file
/// \brief The greeter capability: its concept.

#ifndef snicholls_fixture_concepts_greeter_hpp
#define snicholls_fixture_concepts_greeter_hpp

#include <concepts>

namespace snicholls
{
/// \brief A type that greets: greet() returns a number.
template <class T>
concept greeter = requires(const T& t) {
    { t.greet() } -> std::same_as<int>;
};
}

#endif
//
//  greeter.hpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
/// \file
/// \brief The greeter capability: its virtual twin and the adapter from the concept.

#ifndef snicholls_fixture_interfaces_greeter_hpp
#define snicholls_fixture_interfaces_greeter_hpp


namespace snicholls
{
/// \brief A greeter chosen at run time.
class greeter_interface
{
public:
    /// \brief Destroys it.
    virtual ~greeter_interface() = default;
    /// \brief Greets.
    /// \return a number.
    virtual int greet() const = 0;
};

/// \brief Any model of the concept, through the virtual interface.
/// \tparam T the model.
template <greeter T>
class greeter_adapter final : public greeter_interface
{
public:
    /// \brief Wraps t.
    /// \param t the model.
    explicit greeter_adapter(T t) : t_(t) {}
    /// \brief Greets through the model.
    /// \return what the model returns.
    int greet() const override { return t_.greet(); }

private:
    T t_;
};
}

#endif
//
//  version.hpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
/// \file
/// \brief The fixture's version.

#ifndef snicholls_fixture_version_hpp
#define snicholls_fixture_version_hpp

// #define SNICHOLLS_FIXTURE_VERSION_MAJOR 9 (a comment, not the version)

/// \brief Major version.
#define SNICHOLLS_FIXTURE_VERSION_MAJOR 1
/// \brief Minor version.
#define SNICHOLLS_FIXTURE_VERSION_MINOR 2
/// \brief Patch version.
#define SNICHOLLS_FIXTURE_VERSION_PATCH 3

#endif
//
//  widget.hpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
/// \file
/// \brief A function to test.

#ifndef snicholls_fixture_widget_hpp
#define snicholls_fixture_widget_hpp

//
//  twice.hpp
//  snicholls-tooling test fixture
//
//  Copyright 2010-2026 Saxon Herschel Nicholls
//
/// \file
/// \brief An internal.

#ifndef snicholls_fixture_detail_twice_hpp
#define snicholls_fixture_detail_twice_hpp

namespace snicholls::detail
{
/// \brief Twice x.
/// \param x the value.
/// \return 2x.
constexpr int twice(int x) noexcept { return 2 * x; }
}

#endif

namespace snicholls
{
/// \brief Twice x plus one.
/// \param x the value.
/// \return 2x + 1.
constexpr int widget(int x) noexcept { return detail::twice(x) + 1; }
}

#endif

#endif
