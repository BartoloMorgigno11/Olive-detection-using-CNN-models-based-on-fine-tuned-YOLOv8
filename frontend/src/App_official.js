import React, { useState, useEffect, useRef } from 'react';
import styled from 'styled-components';
import axios from 'axios';
import LinearBuffer from './LinearBuffer'; // Import the loading bar component

const Background = styled.div`
  background:
    radial-gradient(circle at 15% 20%, rgba(196, 215, 133, 0.55), transparent 35%),
    radial-gradient(circle at 85% 80%, rgba(74, 116, 72, 0.5), transparent 40%),
    linear-gradient(135deg, #e8efd3, #9dbb7d 52%, #426b47);
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background-size: cover;
  background-position: center;
`;

const Container = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  color: #3D5F4A;
  background-color: #F2F5D8;
  border: 7px solid #3D5F4A;
  border-radius: 7px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  text-align: center;
  width: auto;
  min-width: 30vw;
  position: relative;
  padding-bottom: 30px;
`;

const Title = styled.h1`
  margin-top: 20px;
`;

const Button = styled.button`
  background-color: #3D5F4A;
  color: white;
  padding: 10px 20px;
  margin-top: 10px; /* Added margin-top to create spacing */
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 16px;
  transition: background-color 0.3s ease;

  &:hover {
    background-color: #214911;
  }
`;

const PreviewContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative; /* Added to position the buttons */
  padding-bottom: 80px; /* Added to avoid overlap */
`;

const PreviewImagesContainer = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr); /* Three-column grid */
  justify-items: center;
  align-items: center;
  gap: 10px;
  margin: 0px 30px 20px 30px;
  padding: 20px;
  background-color: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  position: relative;
`;

const PreviewBox = styled.div`
  position: relative;
  width: 150px;
  height: 150px;
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  overflow: hidden;
  display: flex;
  flex-direction: column;
`;

const RemoveButton = styled.button`
  position: absolute;
  top: 5px;
  right: 5px;
  background-color: white;
  color: black;
  border: none;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  cursor: pointer;
`;

const PreviewImage = styled.img`
  width: 100%;
  height: 100%;
  object-fit: cover;
  flex: 1;
`;

const ImageName = styled.p`
  margin-top: 5px;
  color: black;
  font-size: 14px;
  text-align: center;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

const BottomButtonLeft = styled(Button)`
  position: absolute;
  bottom: 20px;
  left: 30px;
`;

const BottomButtonRight = styled(Button)`
  position: absolute;
  bottom: 20px;
  right: 30px;
`;

// Layout helpers for responsive design
const ResultsContainer = styled.div`
  display: flex;
  flex-direction: column;
  padding: 20px;
  max-width: 90vw;
  margin: 0 auto;

  @media(min-width: 768px) {
    flex-direction: row;
    align-items: flex-start;
    position: relative;
  }
`;

const VerticalLine = styled.div`
  width: 1px;
  background-color: #3D5F4A;
  height: auto;
  margin: 0 20px;

  @media(max-width: 767px) {
    display: none;
  }
`;

const LeftColumn = styled.div`
  flex: 1;
  margin-right: 0;

  @media(min-width: 768px) {
    margin-right: 20px;
  }
`;

const RightColumn = styled.div`
  flex: 1;
  margin-top: 20px;
  display: flex;
  flex-direction: column;

  @media(min-width: 768px) {
    margin-top: 0;
  }
`;

// Set a white background for the summary container
const SummaryContainer = styled.div`
  color: black;
  background-color: white;
  padding: 20px;
  border: 2px solid #3D5F4A;
  border-radius: 5px;
  text-align: center;
  margin-top: 20px;
`;

const SuccessMessage = styled.p`
  font-size: 20px;
  font-weight: bold;
  color: #3D5F4A;
  margin-top: 20px;
`;

const ResultImage = styled.img`
  width: 100%;
  height: auto;
  max-width: 800px;  /* Set a maximum width for the image */
  max-height: 500px; /* Increase the maximum height */
  display: block;
  margin: 0 auto 20px auto;
`;

const PaginationContainer = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 20px;
`;

const PageButton = styled.button`
  background-color: #3D5F4A;
  color: white;
  border: none;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  margin: 0 10px;
  font-size: 24px;
  cursor: pointer;

  &:disabled {
    background-color: grey;
    cursor: not-allowed;
  }
`;

const App = () => {
  const [selectedImages, setSelectedImages] = useState([]);
  const [results, setResults] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isUploadComplete, setIsUploadComplete] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [hidePreview, setHidePreview] = useState(false);
  const [summaryResults, setSummaryResults] = useState(null);
  const [showSuccessMessage, setShowSuccessMessage] = useState(true);
  const [showViewResultsButton, setShowViewResultsButton] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const pollingIntervalRef = useRef(null);

  // Pagination state for results
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 4; // Show four processed results per page

  // Pagination state for previews
  const [previewCurrentPage, setPreviewCurrentPage] = useState(1);
  const previewItemsPerPage = 9; // Keep nine previews per page

  useEffect(() => {
    const cleanFolders = async () => {
      try {
        await axios.post('http://localhost:3001/clean_folders');
        console.log('Folders cleaned successfully.');
      } catch (error) {
        console.error('Error while cleaning folders:', error);
      }
    };
    cleanFolders();

    // Clear the polling interval when the component unmounts
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    setSelectedImages((prevImages) => [...prevImages, ...files]);
    setIsUploadComplete(false);
    setShowResults(false);
    setHidePreview(false);
    setShowSuccessMessage(true);
    setShowViewResultsButton(true);
    setPreviewCurrentPage(1); // Reset preview pagination to the first page
  };

  const handleImageUpload = async () => {
    if (selectedImages.length === 0) {
      alert('No images selected.');
      return;
    }

    setIsAnalyzing(true); // Analysis in progress
    setUploadStatus('Uploading and analyzing images...');
    setProgress(0); // Reset progress bar

    const formData = new FormData();
    selectedImages.forEach((image) => {
      formData.append('files', image);
    });

    try {
      const uploadResponse = await axios.post('http://localhost:3001/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (uploadResponse.status === 200) {
        // Start polling for progress updates
        startProgressPolling();
      } else {
        setUploadStatus('Error during upload or analysis.');
        setIsAnalyzing(false);
      }
    } catch (error) {
      setUploadStatus('Error during upload or analysis.');
      console.error('Error during upload:', error);
      setIsAnalyzing(false);
    }
  };

  const startProgressPolling = () => {
    pollingIntervalRef.current = setInterval(async () => {
      try {
        const response = await axios.get('http://localhost:3001/progress');
        const progressData = response.data;

        setProgress(progressData.percentage);

        if (progressData.percentage >= 100) {
          finalizeAnalysis();
        }
      } catch (error) {
        console.error('Error while polling progress:', error);
        clearInterval(pollingIntervalRef.current);
        setIsAnalyzing(false);
        setUploadStatus('Error during analysis.');
      }
    }, 500); // Poll every 0.5 seconds
  };

  const finalizeAnalysis = () => {
    clearInterval(pollingIntervalRef.current);
    setIsAnalyzing(false);
    setUploadStatus('Analysis completed successfully.');
    setIsUploadComplete(true);
    setHidePreview(true);
    setProgress(100);
  };

  const handleGetResults = async () => {
    try {
      const [resultsResponse, summaryResponse] = await Promise.all([
        axios.get('http://localhost:3001/get_results'),
        axios.get('http://localhost:3001/get_summary_results'),
      ]);
      setResults(resultsResponse.data.results);
      setSummaryResults(summaryResponse.data);
      setShowResults(true);
      setShowSuccessMessage(false);
      setShowViewResultsButton(false);
      setCurrentPage(1); // Reset to the first page
    } catch (error) {
      console.error('Error while fetching results:', error);
    }
  };

  const handleDownloadResults = async () => {
    try {
      const response = await axios.get('http://localhost:3001/download_results', {
        responseType: 'blob', // Required to handle binary content
      });

      const blob = new Blob([response.data], { type: 'application/zip' });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = 'results.zip'; // Default filename
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Error while downloading results:', error);
      alert('An error occurred while downloading the results.');
    }
  };

  // Result pagination helpers
  const indexOfLastItem = currentPage * itemsPerPage;
  const indexOfFirstItem = indexOfLastItem - itemsPerPage;
  const currentResults = results ? results.slice(indexOfFirstItem, indexOfLastItem) : [];

  const totalPages = results ? Math.ceil(results.length / itemsPerPage) : 1;

  const nextPage = () => {
    setCurrentPage((prevPage) => Math.min(prevPage + 1, totalPages));
  };

  const prevPage = () => {
    setCurrentPage((prevPage) => Math.max(prevPage - 1, 1));
  };

  // Preview pagination helpers
  const previewIndexOfLastItem = previewCurrentPage * previewItemsPerPage;
  const previewIndexOfFirstItem = previewIndexOfLastItem - previewItemsPerPage;
  const currentPreviews = selectedImages.slice(previewIndexOfFirstItem, previewIndexOfLastItem);

  const previewTotalPages = Math.ceil(selectedImages.length / previewItemsPerPage);

  const nextPreviewPage = () => {
    setPreviewCurrentPage((prevPage) => Math.min(prevPage + 1, previewTotalPages));
  };

  const prevPreviewPage = () => {
    setPreviewCurrentPage((prevPage) => Math.max(prevPage - 1, 1));
  };

  return (
    <Background>
      <Container>
        <Title>OLIVE DETECTION</Title>

        <input
          type="file"
          id="file-input"
          multiple
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />

        {!hidePreview && selectedImages.length === 0 ? (
          <Button onClick={() => document.getElementById('file-input').click()}>
            Upload Images
          </Button>
        ) : (
          <>
            {!hidePreview && !isAnalyzing && (
              <PreviewContainer>
                <h2>Image Previews</h2>
                <PreviewImagesContainer>
                  {currentPreviews.map((file, index) => (
                    <div key={index}>
                      <PreviewBox>
                        <PreviewImage src={URL.createObjectURL(file)} alt="Image preview" />
                        <RemoveButton onClick={() => {
                          const updatedImages = selectedImages.filter((_, i) => i !== (previewIndexOfFirstItem + index));
                          setSelectedImages(updatedImages);
                          if ((updatedImages.length % previewItemsPerPage === 0) && (previewCurrentPage > 1)) {
                            setPreviewCurrentPage(previewCurrentPage - 1);
                          }
                        }}>
                          x
                        </RemoveButton>
                      </PreviewBox>
                      <ImageName>{file.name}</ImageName>
                    </div>
                  ))}
                </PreviewImagesContainer>

                {selectedImages.length > previewItemsPerPage && (
                  <PaginationContainer>
                    <PageButton onClick={prevPreviewPage} disabled={previewCurrentPage === 1}>
                      &lt;
                    </PageButton>
                    <span>Page {previewCurrentPage} of {previewTotalPages}</span>
                    <PageButton onClick={nextPreviewPage} disabled={previewCurrentPage === previewTotalPages}>
                      &gt;
                    </PageButton>
                  </PaginationContainer>
                )}

                <BottomButtonLeft onClick={() => document.getElementById('file-input').click()}>
                  Upload more images
                </BottomButtonLeft>

                <BottomButtonRight onClick={handleImageUpload}>
                  Start Analysis
                </BottomButtonRight>
              </PreviewContainer>
            )}
          </>
        )}

        {isAnalyzing && (
          <>
            <SuccessMessage>{uploadStatus}</SuccessMessage>
            <LinearBuffer progress={progress} />
          </>
        )}

        {!isAnalyzing && uploadStatus && showSuccessMessage && (
          <SuccessMessage>{uploadStatus}</SuccessMessage>
        )}

        {isUploadComplete && showViewResultsButton && (
          <Button onClick={handleGetResults}>
            View Results
          </Button>
        )}

        {showResults && (
          <>
            <ResultsContainer>
              <LeftColumn>
                <h2>Distribution Charts</h2>

                  <ResultImage src="http://localhost:3001/results/plot/olive_maturity_distribution.png" alt="Maturity distribution chart" />
                  <ResultImage src="http://localhost:3001/results/plot/olive_weight_distribution.png" alt="Weight distribution chart" />

              </LeftColumn>

              <VerticalLine />

              <RightColumn>
                <h2>Processing Results</h2>
                {currentResults.map((result, index) => (
                  <div key={index}>
                    <ResultImage src={`http://localhost:3001/results/${result}`} alt={`Result ${index + 1}`} />
                  </div>
                ))}

                {results && results.length > itemsPerPage && (
                  <PaginationContainer>
                    <PageButton onClick={prevPage} disabled={currentPage === 1}>
                      &lt;
                    </PageButton>
                    <span>Page {currentPage} of {totalPages}</span>
                    <PageButton onClick={nextPage} disabled={currentPage === totalPages}>
                      &gt;
                    </PageButton>
                  </PaginationContainer>
                )}
              </RightColumn>
            </ResultsContainer>

            {/* Summary container and download button positioned below the gallery */}
            {summaryResults && (
              <SummaryContainer>
                <h3>SUMMARY</h3>
                <p>Total detected olives: {summaryResults.total_olives}</p>
                <p>Approximate total olive weight: {summaryResults.total_weight_approx.toFixed(2)} g</p>
                <p>Estimated total weight (olive count * 6 g): {summaryResults.total_weight_average.toFixed(2)} g</p>
                {summaryResults.adjusted_weight_count > 0 && (
                  <p>
                    <strong>Note:</strong> For {summaryResults.adjusted_weight_count} detected olives, the weight was set to 6 grams because the bounding box area was too large for a reliable estimate.
                  </p>
                )}
              </SummaryContainer>
            )}

            <Button onClick={handleDownloadResults}>
              Download Results
            </Button>
          </>
        )}
      </Container>
    </Background>
  );
};

export default App;
