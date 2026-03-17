package com.chaos.app.controller;

import com.chaos.app.dto.ApiResponse;
import com.chaos.app.model.Product;
import com.chaos.app.service.ProductService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class ProductController {

    private final ProductService productService;

    // ─── Health ────────────────────────────────────────────────────────────────

    /**
     * Simple application-level health endpoint (in addition to Spring Actuator).
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of(
            "status", "UP",
            "service", "chaos-app",
            "version", "1.0.0"
        ));
    }

    // ─── Products ──────────────────────────────────────────────────────────────

    /**
     * GET /api/products
     * Returns all products, optionally filtered by category query param.
     */
    @GetMapping("/products")
    public ResponseEntity<ApiResponse<List<Product>>> getAllProducts(
            @RequestParam(required = false) String category) {

        List<Product> products = (category != null && !category.isBlank())
                ? productService.getProductsByCategory(category)
                : productService.getAllProducts();

        log.debug("GET /api/products – returning {} items", products.size());
        return ResponseEntity.ok(ApiResponse.ok(products, products, "Products fetched successfully"));
    }

    /**
     * GET /api/products/{id}
     * Returns a single product by its MongoDB ObjectId.
     */
    @GetMapping("/products/{id}")
    public ResponseEntity<ApiResponse<Product>> getProductById(@PathVariable String id) {
        return productService.getProductById(id)
                .map(p -> ResponseEntity.ok(ApiResponse.ok(p, "Product found")))
                .orElseGet(() -> ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(ApiResponse.error("Product not found with id: " + id)));
    }

    /**
     * GET /api/products/category/{category}
     * Returns products filtered by category (case-insensitive).
     */
    @GetMapping("/products/category/{category}")
    public ResponseEntity<ApiResponse<List<Product>>> getByCategory(
            @PathVariable String category) {

        List<Product> products = productService.getProductsByCategory(category);
        return ResponseEntity.ok(ApiResponse.ok(products, products,
                "Products in category '" + category + "' fetched successfully"));
    }

    /**
     * POST /api/products
     * Creates a new product.
     */
    @PostMapping("/products")
    public ResponseEntity<ApiResponse<Product>> createProduct(@RequestBody Product product) {
        Product saved = productService.createProduct(product);
        log.info("Created product: {}", saved.getId());
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.ok(saved, "Product created successfully"));
    }

    /**
     * PUT /api/products/{id}
     * Updates an existing product.
     */
    @PutMapping("/products/{id}")
    public ResponseEntity<ApiResponse<Product>> updateProduct(
            @PathVariable String id,
            @RequestBody Product product) {

        return productService.updateProduct(id, product)
                .map(p -> ResponseEntity.ok(ApiResponse.ok(p, "Product updated successfully")))
                .orElseGet(() -> ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(ApiResponse.error("Product not found with id: " + id)));
    }

    /**
     * DELETE /api/products/{id}
     * Deletes a product by its ID.
     */
    @DeleteMapping("/products/{id}")
    public ResponseEntity<ApiResponse<Void>> deleteProduct(@PathVariable String id) {
        boolean deleted = productService.deleteProduct(id);
        if (deleted) {
            return ResponseEntity.ok(ApiResponse.ok(null, "Product deleted successfully"));
        }
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ApiResponse.error("Product not found with id: " + id));
    }
}
