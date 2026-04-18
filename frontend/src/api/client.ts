import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api",
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ??
      error.response?.data?.message ??
      error.message ??
      "An unexpected error occurred";

    console.error("[API Error]", {
      status: error.response?.status,
      url: error.config?.url,
      message,
    });

    return Promise.reject(new Error(message));
  },
);

export default apiClient;
