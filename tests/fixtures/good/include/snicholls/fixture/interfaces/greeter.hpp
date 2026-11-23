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

#include <snicholls/fixture/concepts/greeter.hpp>

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
