import React from 'react';
import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';

const LinearBuffer = ({ progress }) => {
  return (
    <Box sx={{ width: '80%', margin: '20px auto' }}>
      <LinearProgress
        variant="determinate"
        value={progress}
        sx={{
          height: 10,
          borderRadius: 5,
          '& .MuiLinearProgress-bar': {
            backgroundColor: 'darkgreen',
          },
          backgroundColor: '#e0e0e0',
        }}
      />
    </Box>
  );
};

export default LinearBuffer;
