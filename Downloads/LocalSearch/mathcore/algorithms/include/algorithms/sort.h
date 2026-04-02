#pragma once
#include "core/types.h"

namespace mathcore {
namespace algorithms {

void sort_vector(core::Vector& vec);
void sort_matrix_rows(core::Matrix& mat);
int binary_search(const core::Vector& vec, double target);

} // namespace algorithms
} // namespace mathcore
