#pragma once
#include <vector>
#include <cstddef>

namespace mathcore {
namespace core {

class Matrix {
public:
    Matrix(size_t rows, size_t cols);

    double& at(size_t row, size_t col);
    const double& at(size_t row, size_t col) const;

    size_t rows() const { return rows_; }
    size_t cols() const { return cols_; }

    Matrix operator+(const Matrix& other) const;

private:
    size_t rows_;
    size_t cols_;
    std::vector<double> data_;
};

class Vector {
public:
    explicit Vector(size_t size);

    double& operator[](size_t i) { return data_[i]; }
    const double& operator[](size_t i) const { return data_[i]; }

    size_t size() const { return data_.size(); }

private:
    std::vector<double> data_;
};

} // namespace core
} // namespace mathcore
