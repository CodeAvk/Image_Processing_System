// App.js
import React, { useState } from "react";
import { ThemeProvider, createTheme, styled } from "@mui/material/styles";
import {
  Container,
  Paper,
  Button,
  Typography,
  CircularProgress,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CssBaseline,
  AppBar,
  Toolbar,
  Link,
  LinearProgress,
} from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import { ToastContainer, toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

// Create Ocean theme
const oceanTheme = createTheme({
  palette: {
    mode: "dark",
    primary: {
      main: "#0ea5e9", // sky-500
      light: "#38bdf8", // sky-400
      dark: "#0284c7", // sky-600
    },
    secondary: {
      main: "#06b6d4", // cyan-500
    },
    background: {
      default: "#0f172a", // slate-900
      paper: "#1e293b", // slate-800
    },
    text: {
      primary: "#f1f5f9", // slate-100
      secondary: "#cbd5e1", // slate-300
    },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          backgroundColor: "#1e293b", // slate-800
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: "#1e293b", // slate-800
          backgroundImage: "none",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          textTransform: "none",
          padding: "10px 20px",
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderColor: "rgba(203, 213, 225, 0.1)", // slate-300 with opacity
        },
      },
    },
  },
});

const VisuallyHiddenInput = styled("input")({
  clip: "rect(0 0 0 0)",
  clipPath: "inset(50%)",
  height: 1,
  overflow: "hidden",
  position: "absolute",
  bottom: 0,
  left: 0,
  whiteSpace: "nowrap",
  width: 1,
});

const StyledPaper = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(3),
  marginBottom: theme.spacing(3),
  borderRadius: theme.spacing(1),
  boxShadow:
    "0 4px 6px -1px rgba(14, 165, 233, 0.1), 0 2px 4px -2px rgba(14, 165, 233, 0.1)",
}));

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [requestId, setRequestId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [processingStatus, setProcessingStatus] = useState(null);
  const [products, setProducts] = useState([]);

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file && file.type === "text/csv") {
      setSelectedFile(file);
      toast.success("CSV file selected successfully");
    } else {
      toast.error("Please select a valid CSV file");
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      toast.error("Please select a file first");
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch("http://localhost:5000/upload", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      if (response.ok) {
        setRequestId(data.request_id);
        toast.success("File uploaded successfully");
        checkStatus(data.request_id);
      } else {
        throw new Error(data.error);
      }
    } catch (error) {
      toast.error(`Upload failed: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const checkStatus = async (id) => {
    try {
      const response = await fetch(`http://localhost:5000/status/${id}`);
      const data = await response.json();

      if (response.ok) {
        setProcessingStatus(data.status);
        if (data.products) {
          setProducts(data.products);
        }

        if (data.status === "processing") {
          setTimeout(() => checkStatus(id), 5000);
        } else if (data.status === "completed") {
          toast.success("Processing completed!");
        } else if (data.status === "failed") {
          toast.error("Processing failed");
        }
      }
    } catch (error) {
      toast.error(`Status check failed: ${error.message}`);
    }
  };

  return (
    <ThemeProvider theme={oceanTheme}>
      <CssBaseline />
      <ToastContainer position="top-right" theme="dark" />
      <AppBar position="static" elevation={0}>
        <Toolbar>
          <Typography variant="h6" component="div">
            Image Processing System
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <StyledPaper>
          <Box sx={{ mb: 3 }}>
            <Button
              component="label"
              variant="contained"
              startIcon={<CloudUploadIcon />}
              sx={{ mb: 2 }}
            >
              Select CSV File
              <VisuallyHiddenInput
                type="file"
                onChange={handleFileSelect}
                accept=".csv"
              />
            </Button>

            {selectedFile && (
              <Typography variant="body1" sx={{ mt: 2 }}>
                Selected file: {selectedFile.name}
              </Typography>
            )}
          </Box>

          <Button
            variant="contained"
            onClick={handleUpload}
            disabled={!selectedFile || loading}
          >
            {loading ? <CircularProgress size={24} sx={{ mr: 1 }} /> : null}
            Upload and Process
          </Button>
        </StyledPaper>

        {requestId && (
          <StyledPaper>
            <Typography variant="h6" gutterBottom>
              Request ID: {requestId}
            </Typography>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body1" gutterBottom>
                Status: {processingStatus}
              </Typography>
              {processingStatus === "processing" && (
                <LinearProgress sx={{ mt: 1 }} />
              )}
            </Box>

            {products.length > 0 && (
              <TableContainer component={Paper} sx={{ mt: 3 }}>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Serial Number</TableCell>
                      <TableCell>Product Name</TableCell>
                      <TableCell>Input URLs</TableCell>
                      <TableCell>Output URLs</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {products.map((product) => (
                      <TableRow key={product.serial_number}>
                        <TableCell>{product.serial_number}</TableCell>
                        <TableCell>{product.product_name}</TableCell>
                        <TableCell>
                          {product.input_urls.map((url, i) => (
                            <Link
                              key={i}
                              href={url}
                              target="_blank"
                              rel="noopener"
                              sx={{ display: "block", mb: 0.5 }}
                            >
                              {url}
                            </Link>
                          ))}
                        </TableCell>
                        <TableCell>
                          {product.output_urls.map((url, i) => (
                            <Link
                              key={i}
                              href={url}
                              target="_blank"
                              rel="noopener"
                              sx={{ display: "block", mb: 0.5 }}
                            >
                              {url}
                            </Link>
                          ))}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </StyledPaper>
        )}
      </Container>
    </ThemeProvider>
  );
}

export default App;
