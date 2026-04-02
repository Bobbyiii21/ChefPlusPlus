#pragma once
#include "core/types.h"

namespace mathcore {
namespace algorithms {

double reduce_sum(const core::Vector& vec);
double reduce_product(const core::Vector& vec);
double reduce_max(const core::Vector& vec);
double reduce_min(const core::Vector& vec);

} // namespace algorithms
} // namespace mathcore
