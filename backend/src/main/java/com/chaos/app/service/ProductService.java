package com.chaos.app.service;

import com.chaos.app.model.Product;
import com.chaos.app.repository.ProductRepository;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

@Slf4j
@Service
@RequiredArgsConstructor
public class ProductService {

    private final ProductRepository productRepository;

    /**
     * Seed sample data on startup if the collection is empty.
     */
    @PostConstruct
    public void seedData() {
        if (productRepository.count() == 0) {
            log.info("Seeding sample product data...");
            List<Product> products = List.of(
                Product.builder()
                    .name("MacBook Pro 14\"")
                    .category("electronics")
                    .price(1999.99)
                    .stock(25)
                    .status("ACTIVE")
                    .description("Apple M3 Pro chip, 18GB RAM, 512GB SSD")
                    .build(),
                Product.builder()
                    .name("Sony WH-1000XM5")
                    .category("electronics")
                    .price(349.99)
                    .stock(80)
                    .status("ACTIVE")
                    .description("Industry-leading noise cancelling wireless headphones")
                    .build(),
                Product.builder()
                    .name("Ergonomic Office Chair")
                    .category("furniture")
                    .price(529.00)
                    .stock(15)
                    .status("ACTIVE")
                    .description("Lumbar support, adjustable armrests, mesh back")
                    .build(),
                Product.builder()
                    .name("Standing Desk 60\"")
                    .category("furniture")
                    .price(799.00)
                    .stock(0)
                    .status("OUT_OF_STOCK")
                    .description("Electric height-adjustable, dual motor")
                    .build(),
                Product.builder()
                    .name("Docker & Kubernetes in Action")
                    .category("books")
                    .price(49.99)
                    .stock(200)
                    .status("ACTIVE")
                    .description("Comprehensive guide to container orchestration")
                    .build(),
                Product.builder()
                    .name("Chaos Engineering: System Resiliency")
                    .category("books")
                    .price(44.99)
                    .stock(150)
                    .status("ACTIVE")
                    .description("Building confidence in system behavior through experiments")
                    .build()
            );
            productRepository.saveAll(products);
            log.info("Seeded {} products into MongoDB.", products.size());
        } else {
            log.info("Products already exist, skipping seed.");
        }
    }

    public List<Product> getAllProducts() {
        return productRepository.findAll();
    }

    public Optional<Product> getProductById(String id) {
        return productRepository.findById(id);
    }

    public List<Product> getProductsByCategory(String category) {
        return productRepository.findByCategory(category.toLowerCase());
    }

    public List<Product> getProductsByStatus(String status) {
        return productRepository.findByStatus(status.toUpperCase());
    }

    public Product createProduct(Product product) {
        if (product.getStatus() == null) {
            product.setStatus("ACTIVE");
        }
        return productRepository.save(product);
    }

    public Optional<Product> updateProduct(String id, Product updated) {
        return productRepository.findById(id).map(existing -> {
            existing.setName(updated.getName());
            existing.setCategory(updated.getCategory());
            existing.setPrice(updated.getPrice());
            existing.setStock(updated.getStock());
            existing.setStatus(updated.getStatus());
            existing.setDescription(updated.getDescription());
            return productRepository.save(existing);
        });
    }

    public boolean deleteProduct(String id) {
        if (productRepository.existsById(id)) {
            productRepository.deleteById(id);
            return true;
        }
        return false;
    }
}
