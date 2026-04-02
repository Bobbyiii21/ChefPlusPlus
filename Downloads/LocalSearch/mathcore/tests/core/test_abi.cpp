#include "core/types.h"
#include <cassert>

int main() {
    mathcore::core::Matrix m(2, 2);
    mathcore::core::Vector v(4);

    assert(m.rows() == 2);
    assert(m.cols() == 2);
    assert(v.size() == 4);

    return 0;
}
