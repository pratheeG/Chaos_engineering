package com.chaos.app.repository;

import com.chaos.app.model.Product;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ProductRepository extends MongoRepository<Product, String> {

    List<Product> findByCategory(String category);

    List<Product> findByStatus(String status);

    List<Product> findByCategoryAndStatus(String category, String status);

    boolean existsByName(String name);
}
