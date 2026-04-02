#include "core/types.h"
#include <cassert>
#include <stdexcept>

int main() {
    mathcore::core::Matrix m(3, 3);
    m.at(0, 0) = 1.0;
    m.at(1, 1) = 2.0;
    m.at(2, 2) = 3.0;

    assert(m.at(0, 0) == 1.0);
    assert(m.at(1, 1) == 2.0);
    assert(m.at(2, 2) == 3.0);
    assert(m.rows() == 3);
    assert(m.cols() == 3);

    mathcore::core::Matrix a(2, 2);
    mathcore::core::Matrix b(2, 2);
    a.at(0, 0) = 1.0;
    b.at(0, 0) = 2.0;
    mathcore::core::Matrix c = a + b;
    assert(c.at(0, 0) == 3.0);

    bool threw = false;
    try { mathcore::core::Matrix bad(0, 1); }
    catch (const std::invalid_argument&) { threw = true; }
    assert(threw);

    return 0;
}
