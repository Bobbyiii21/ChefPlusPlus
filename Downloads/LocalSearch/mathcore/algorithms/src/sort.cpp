#include "algorithms/sort.h"
#include "core/types.h"
#include <algorithm>
#include <vector>

namespace mathcore {
namespace algorithms {

void sort_vector(core::Vector& vec) {
    std::sort(&vec[0], &vec[0] + vec.size());
}

void sort_matrix_rows(core::Matrix& mat) {
    for (size_t row = 0; row < mat.rows(); ++row) {
        std::vector<double> temp(mat.cols());
        for (size_t col = 0; col < mat.cols(); ++col) {
            temp[col] = mat.at(row, col);
        }
        std::sort(temp.begin(), temp.end());
        for (size_t col = 0; col < mat.cols(); ++col) {
            mat.at(row, col) = temp[col];
        }
    }
}

int binary_search(const core::Vector& vec, double target) {
    size_t left = 0;
    size_t right = vec.size();
    while (left < right) {
        size_t mid = left + (right - left) / 2;
        if (vec[mid] == target) return static_cast<int>(mid);
        if (vec[mid] < target) left = mid + 1;
        else right = mid;
    }
    return -1;
}

} // namespace algorithms
} // namespace mathcore
