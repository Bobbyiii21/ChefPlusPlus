#pragma once
#include "core/types.h"

namespace mathcore {
namespace analytics {

double mean(const core::Vector& vec);
double variance(const core::Vector& vec);
double std_deviation(const core::Vector& vec);

double sum(const core::Vector& vec);
double min_val(const core::Vector& vec);
double max_val(const core::Vector& vec);

core::Vector column_means(const core::Matrix& mat);

} // namespace analytics
} // namespace mathcore
