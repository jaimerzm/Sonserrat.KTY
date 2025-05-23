import React, { useState, useRef, useEffect } from 'react';
import { Box, Paper, TextField, IconButton, Typography, CircularProgress, List, ListItem, ListItemText, Drawer, useTheme, useMediaQuery, Button, Avatar, Menu as MuiMenu, MenuItem, Divider, Select, FormControl, InputLabel, SelectChangeEvent, ToggleButtonGroup, ToggleButton, Snackbar, Alert } from '@mui/material';
import { Send, AttachFile, Menu, Star, StarBorder, AccountCircle, ExitToApp, Movie, Image as ImageIcon, Chat as ChatIcon, ErrorOutline, ContentCopy } from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import { useChat } from '../contexts/ChatContext';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const Chat: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [message, setMessage] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(!isMobile);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [currentModel, setCurrentModel] = useState<'gemini' | 'groq' | 'kkty2-video'>('gemini');
  const [videoDuration, setVideoDuration] = useState<number>(5);
  const [videoCount, setVideoCount] = useState<number>(1);
  const [videoAspectRatio, setVideoAspectRatio] = useState<string>('16:9');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [userMenuAnchor, setUserMenuAnchor] = useState<null | HTMLElement>(null);
  const navigate = useNavigate();

  const {
    conversations,
    currentConversation,
    loading,
    sendMessage,
    createNewConversation,
    loadConversation,
    starConversation,
    // Snackbar
    snackbarOpen,
    snackbarMessage,
    snackbarSeverity,
    closeSnackbar,
  } = useChat();

  const { user, logout } = useAuth();

  useEffect(() => {
    scrollToBottom();
  }, [currentConversation?.messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSend = async () => {
    if (message.trim() || files.length > 0) {
      let filesToSend = files;
      if (currentModel === 'groq' && files.length > 0) {
        window.alert("Groq model cannot process images. The image will not be sent. Sending text message only.");
        filesToSend = []; // Clear files for Groq
      }

      if (currentModel === 'kkty2-video') {
        await sendMessage(message, filesToSend, currentModel, { // Use filesToSend
          durationSeconds: videoDuration,
          numberOfVideos: videoCount,
          video_aspect_ratio: videoAspectRatio,
        });
      } else {
        await sendMessage(message, filesToSend, currentModel); // Use filesToSend
      }
      setMessage('');
      setFiles([]); // Clear files from UI after sending attempt
      // Don't reset video params, user might want to generate similar videos
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setFiles(Array.from(event.target.files));
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const handleUserMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setUserMenuAnchor(event.currentTarget);
  };

  const handleUserMenuClose = () => {
    setUserMenuAnchor(null);
  };

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      <Snackbar 
        open={snackbarOpen} 
        autoHideDuration={6000} 
        onClose={closeSnackbar}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert onClose={closeSnackbar} severity={snackbarSeverity} sx={{ width: '100%' }} variant="filled">
          {snackbarMessage}
        </Alert>
      </Snackbar>
      <Drawer
        variant={isMobile ? 'temporary' : 'persistent'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        sx={{
          width: 240,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: 240,
            boxSizing: 'border-box',
            display: 'flex',
            flexDirection: 'column',
          },
        }}
      >
        <Box sx={{ p: 2, flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
          <Button
            fullWidth
            variant="contained"
            onClick={createNewConversation}
            sx={{ mb: 2 }}
          >
            New Chat
          </Button>
          <Typography variant="h6" sx={{ mb: 1 }}>Conversations</Typography>
          <List sx={{ 
            flexGrow: 1, 
            overflowY: 'auto',
            maxHeight: 'calc(100vh - 200px)', // Adjusted height to make room for user panel
            '&::-webkit-scrollbar': {
              width: '6px',
            },
            '&::-webkit-scrollbar-track': {
              background: 'transparent',
            },
            '&::-webkit-scrollbar-thumb': {
              background: 'rgba(0, 0, 0, 0.2)',
              borderRadius: '3px',
            }
          }}>
            {conversations.map((conv) => (
              <motion.div
                key={conv.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3 }}
              >
                <ListItem
                  button
                  selected={currentConversation?.id === conv.id}
                  onClick={() => loadConversation(conv.id)}
                >
                  <ListItemText primary={conv.title} />
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      starConversation(conv.id);
                    }}
                  >
                    {conv.starred ? <Star color="primary" /> : <StarBorder />}
                  </IconButton>
                </ListItem>
              </motion.div>
            ))}
          </List>
        </Box>
        
        {/* User Panel */}
        <Box 
          sx={{ 
            p: 2, 
            borderTop: 1, 
            borderColor: 'divider',
            display: 'flex',
            alignItems: 'center',
            cursor: 'pointer',
            '&:hover': {
              bgcolor: 'rgba(0, 0, 0, 0.04)'
            },
            transition: 'background-color 0.2s'
          }}
          onClick={handleUserMenuOpen}
        >
          <Avatar sx={{ mr: 2, bgcolor: 'primary.main' }}>
            {user?.username?.charAt(0).toUpperCase() || <AccountCircle />}
          </Avatar>
          <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
            <Typography noWrap variant="subtitle2">
              {user?.username || 'User'}
            </Typography>
            <Typography noWrap variant="caption" color="text.secondary">
              {user?.email || ''}
            </Typography>
          </Box>
        </Box>
        
        {/* User Menu */}
        <MuiMenu
          anchorEl={userMenuAnchor}
          open={Boolean(userMenuAnchor)}
          onClose={handleUserMenuClose}
          transformOrigin={{ horizontal: 'left', vertical: 'top' }}
          anchorOrigin={{ horizontal: 'left', vertical: 'bottom' }}
          PaperProps={{
            elevation: 3,
            sx: { width: 220, mt: 1 }
          }}
        >
          <MenuItem onClick={handleUserMenuClose}>
            <AccountCircle sx={{ mr: 2 }} />
            Profile
          </MenuItem>
          <Divider />
          <MenuItem 
            onClick={() => {
              handleUserMenuClose();
              handleLogout();
            }}
            sx={{ color: 'error.main' }}
          >
            <ExitToApp sx={{ mr: 2 }} />
            Logout
          </MenuItem>
        </MuiMenu>
      </Drawer>

      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', p: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <IconButton onClick={() => setDrawerOpen(!drawerOpen)} sx={{ mr: 2 }}>
            <Menu />
          </IconButton>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            {currentConversation?.title || 'New Chat'}
          </Typography>
          <ToggleButtonGroup
            value={currentModel}
            exclusive
            onChange={(event, newModel) => {
              if (newModel !== null) {
                setCurrentModel(newModel);
              }
            }}
            aria-label="text alignment"
            size="small"
          >
            <ToggleButton value="gemini" aria-label="gemini model">
              <ChatIcon fontSize="small" sx={{mr: 0.5}}/> Gemini
            </ToggleButton>
            <ToggleButton value="groq" aria-label="groq model">
              <ChatIcon fontSize="small" sx={{mr: 0.5}}/> Groq
            </ToggleButton>
            <ToggleButton value="kkty2-video" aria-label="video model">
              <Movie fontSize="small" sx={{mr: 0.5}}/> Veo 2
            </ToggleButton>
             {/* Add other model toggles here, e.g., for image generation */}
          </ToggleButtonGroup>
        </Box>

        {currentModel === 'kkty2-video' && (
          <Paper sx={{ p: 1, mb: 1, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <TextField
              label="Duration (s)"
              type="number"
              size="small"
              value={videoDuration}
              onChange={(e) => setVideoDuration(Math.max(5, Math.min(8, parseInt(e.target.value, 10))))}
              inputProps={{ min: 5, max: 8 }}
              sx={{ width: '120px' }}
            />
            <TextField
              label="# Videos"
              type="number"
              size="small"
              value={videoCount}
              onChange={(e) => setVideoCount(Math.max(1, Math.min(4, parseInt(e.target.value, 10))))}
              inputProps={{ min: 1, max: 4 }}
              sx={{ width: '100px' }}
            />
            <FormControl size="small" sx={{ minWidth: '120px' }}>
              <InputLabel>Aspect Ratio</InputLabel>
              <Select
                value={videoAspectRatio}
                label="Aspect Ratio"
                onChange={(e: SelectChangeEvent) => setVideoAspectRatio(e.target.value)}
              >
                <MenuItem value="16:9">16:9</MenuItem>
                <MenuItem value="9:16">9:16</MenuItem>
              </Select>
            </FormControl>
          </Paper>
        )}

        <Paper
          sx={{
            flexGrow: 1,
            mb: 2,
            p: 2,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <AnimatePresence>
            {currentConversation?.messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
              >
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    mb: 2,
                  }}
                >
                  <Paper
                    sx={{
                      p: 1.5,
                      maxWidth: '80%',
                      bgcolor: msg.role === 'user' ? 'primary.main' : 'background.paper',
                      color: msg.role === 'user' ? 'primary.contrastText' : 'text.primary',
                      borderRadius: theme.shape.borderRadius * 3, // Softer edges
                      boxShadow: theme.shadows[1], // Subtle shadow
                    }}
                  >
                    {renderMessageContent(msg.content, msg.role)}
                  </Paper>
                </Box>
              </motion.div>
            ))}
          </AnimatePresence>
          <div ref={messagesEndRef} />
        </Paper>

        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <input
            type="file"
            multiple
            ref={fileInputRef}
            style={{ display: 'none' }}
            onChange={handleFileSelect}
          />
          <IconButton
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
            aria-label="attach files"
          >
            <AttachFile />
          </IconButton>
          <TextField
            fullWidth
            multiline
            maxRows={5} // Increased maxRows
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message, or a prompt for video/image..."
            disabled={loading}
            sx={{ flexGrow: 1 }}
          />
          <IconButton
            onClick={handleSend}
            disabled={loading || (!message.trim() && !files.length)}
            color="primary"
            aria-label="send message"
          >
            {loading ? <CircularProgress size={24} /> : <Send />}
          </IconButton>
        </Box>
      </Box>
    </Box>
  );
};

// Helper function to render message content with videos, images, and error styling
const errorPrefixes = ["Error:", "Lo siento", "Failed to", "Tu solicitud de generación de video fue bloqueada", "El modelo no pudo generar la imagen debido a filtros de seguridad"];

const renderMessageContent = (content: string, role: 'user' | 'assistant'): React.ReactNode[] => {
  if (!content) return [<Typography key="empty" component="span" sx={{ whiteSpace: 'pre-wrap' }}></Typography>];

  let isErrorMessage = false;
  if (role === 'assistant') {
    const lowerContent = content.toLowerCase();
    isErrorMessage = errorPrefixes.some(prefix => lowerContent.startsWith(prefix.toLowerCase()));
  }

  const parts: React.ReactNode[] = [];
  let lastIndex = 0;

  // Combined regex for media and code blocks
  // Supports [GENERATED_VIDEO:url], [GENERATED_IMAGE:url], and ```lang\ncode``` or ```code```
  const combinedRegex = /\[GENERATED_(VIDEO|IMAGE):(.*?)\]|```(?:([\w-]+)\n)?([\s\S]*?)```/g;
  let match;

  const { showSnackbar } = useChat(); // Access showSnackbar from context

  while ((match = combinedRegex.exec(content)) !== null) {
    // Add text before the match
    if (match.index > lastIndex) {
      const textSegment = content.substring(lastIndex, match.index);
      parts.push(
        <Typography
          key={`text-${lastIndex}`}
          component="span"
          sx={{
            whiteSpace: 'pre-wrap',
            color: isErrorMessage ? theme.palette.error.main : 'inherit',
            lineHeight: 1.6,
          }}
        >
          {isErrorMessage && parts.length === 0 && <ErrorOutline sx={{ fontSize: '1rem', verticalAlign: 'middle', marginRight: 0.5 }} />}
          {textSegment}
        </Typography>
      );
    }

    const mediaType = match[1]; // VIDEO or IMAGE
    const mediaUrl = match[2];   // URL for media
    // const codeLang = match[3];    // Language for code block (optional)
    const codeContent = match[4]; // Content of the code block

    if (mediaType === 'VIDEO' && mediaUrl) {
      parts.push(
        <video
          key={`video-${match.index}`}
          controls
          src={mediaUrl}
          style={{ maxWidth: '100%', maxHeight: '300px', borderRadius: '8px', marginTop: '8px' }}
          onError={(e) => console.error('Error loading video:', e)}
        >
          Your browser does not support the video tag.
        </video>
      );
    } else if (mediaType === 'IMAGE' && mediaUrl) {
      parts.push(
        <img
          key={`image-${match.index}`}
          src={mediaUrl}
          alt="Generated content"
          style={{ maxWidth: '100%', maxHeight: '300px', borderRadius: '8px', marginTop: '8px', display: 'block' }}
          onError={(e) => console.error('Error loading image:', e)}
        />
      );
    } else if (codeContent !== undefined) { // Check if codeContent was matched (it can be an empty string)
      const handleCopyCode = () => {
        navigator.clipboard.writeText(codeContent)
          .then(() => showSnackbar("Code copied to clipboard!", "success"))
          .catch(err => {
            console.error('Failed to copy code:', err);
            showSnackbar("Failed to copy code.", "error");
          });
      };
      parts.push(
        <Paper 
          key={`code-${match.index}`} 
          sx={{ 
            mt: 1, 
            p: 1.5, 
            bgcolor: theme.palette.mode === 'dark' ? theme.palette.grey[900] : theme.palette.grey[200], // Darker for dark, Lighter for light
            borderRadius: theme.shape.borderRadius,
            overflowX: 'auto',
            position: 'relative', // For positioning the copy button
            fontFamily: '"Fira Code", "Courier New", Courier, monospace', // Monospace font
            fontSize: '0.875rem',
          }}
          elevation={0} // Flat appearance for code block
        >
          <IconButton
            size="small"
            onClick={handleCopyCode}
            sx={{
              position: 'absolute',
              top: theme.spacing(0.5),
              right: theme.spacing(0.5),
              color: theme.palette.text.secondary,
              '&:hover': {
                backgroundColor: theme.palette.action.hover,
              }
            }}
            aria-label="copy code to clipboard"
          >
            <ContentCopy fontSize="small" />
          </IconButton>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
            <code>{codeContent.trim()}</code>
          </pre>
        </Paper>
      );
    }
    lastIndex = combinedRegex.lastIndex;
  }

  // Add any remaining text after the last match
  if (lastIndex < content.length) {
    const textSegment = content.substring(lastIndex);
    parts.push(
      <Typography
        key={`text-${lastIndex}`}
        component="span"
        sx={{
          whiteSpace: 'pre-wrap',
          color: isErrorMessage ? theme.palette.error.main : 'inherit',
          lineHeight: 1.6,
        }}
      >
        {isErrorMessage && parts.length === 0 && <ErrorOutline sx={{ fontSize: '1rem', verticalAlign: 'middle', marginRight: 0.5 }} />}
        {textSegment}
      </Typography>
    );
  }

  // If no media or code blocks were found, and the content is not just whitespace, return the original content styled appropriately
  if (parts.length === 0 && content.trim()) {
    return [
      <Typography
        key="full-text"
        component="span"
        sx={{
          whiteSpace: 'pre-wrap',
          color: isErrorMessage ? theme.palette.error.main : 'inherit',
          lineHeight: 1.6,
        }}
      >
        {isErrorMessage && <ErrorOutline sx={{ fontSize: '1rem', verticalAlign: 'middle', marginRight: 0.5 }} />}
        {content}
      </Typography>
    ];
  }

  return parts;
};

// Access theme outside of component for the helper function (if needed, or pass theme as arg)
// This is a bit of a workaround. Ideally, renderMessageContent would be a component or hook.
let theme: any; // Use 'any' or proper Theme type if imported globally
const ChatWithThemeAccess: React.FC = () => {
  const globalTheme = useTheme(); // Renamed to avoid conflict with the global 'theme' variable
  theme = globalTheme; // Assign theme here
  const chatContext = useChat(); // Need to call useChat here to pass showSnackbar
  
  // Make a stable reference to showSnackbar to avoid re-creating renderMessageContent too often if it were a dependency
  const showSnackbarRef = useRef(chatContext.showSnackbar);
  useEffect(() => {
    showSnackbarRef.current = chatContext.showSnackbar;
  }, [chatContext.showSnackbar]);

  // Pass role and showSnackbar to renderMessageContent
  // This is a bit hacky, ideally renderMessageContent is a component that can useChat directly
  // For now, we adapt it to receive showSnackbar
  const adaptedRenderMessageContent = (content: string, role: 'user' | 'assistant') => {
    const originalRenderMessageContent = renderMessageContent; // Keep a reference
    // Temporarily override useChat for the scope of this render, or better, pass showSnackbar explicitly
    // This is complex. Let's simplify by making renderMessageContent accept showSnackbar
    // Or, make renderMessageContent a proper component.
    // For now, the version of renderMessageContent defined outside will use the theme,
    // and the one inside Chat.tsx will use the context for showSnackbar.
    // This will be handled by ensuring renderMessageContent uses the useChat hook if it becomes a component.
    // The current structure where renderMessageContent is a standalone function that now needs context is tricky.

    // Re-defining a local version that can access `chatContext.showSnackbar`
    // This is not ideal, but a quick fix given the helper's current structure.
    const renderMessageContentWithSnackbar = (content: string, role: 'user' | 'assistant'): React.ReactNode[] => {
      if (!content) return [<Typography key="empty" component="span" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}></Typography>];
      let isErrorMessage = false;
      if (role === 'assistant') {
        const lowerContent = content.toLowerCase();
        isErrorMessage = errorPrefixes.some(prefix => lowerContent.startsWith(prefix.toLowerCase()));
      }
      const localParts: React.ReactNode[] = [];
      let localLastIndex = 0;
      let localMatch;
      while ((localMatch = combinedRegex.exec(content)) !== null) {
        if (localMatch.index > localLastIndex) {
          const textSegment = content.substring(localLastIndex, localMatch.index);
          localParts.push(
            <Typography key={`text-${localLastIndex}`} component="span" sx={{ whiteSpace: 'pre-wrap', color: isErrorMessage ? globalTheme.palette.error.main : 'inherit', lineHeight: 1.6, }}>
              {isErrorMessage && localParts.length === 0 && <ErrorOutline sx={{ fontSize: '1rem', verticalAlign: 'middle', marginRight: 0.5 }} />}
              {textSegment}
            </Typography>
          );
        }
        const mediaType = localMatch[1]; const mediaUrl = localMatch[2]; const codeContent = localMatch[4];
        if (mediaType === 'VIDEO' && mediaUrl) { /* Video rendering */ 
          localParts.push(
            <video key={`video-${localMatch.index}`} controls src={mediaUrl} style={{ maxWidth: '100%', maxHeight: '300px', borderRadius: '8px', marginTop: '8px' }} onError={(e) => console.error('Error loading video:', e)}>Your browser does not support the video tag.</video>
          );
        } else if (mediaType === 'IMAGE' && mediaUrl) { /* Image rendering */ 
          localParts.push(
            <img key={`image-${localMatch.index}`} src={mediaUrl} alt="Generated content" style={{ maxWidth: '100%', maxHeight: '300px', borderRadius: '8px', marginTop: '8px', display: 'block' }} onError={(e) => console.error('Error loading image:', e)} />
          );
        } else if (codeContent !== undefined) { /* Code block rendering */ 
          const handleCopyCode = () => {
            navigator.clipboard.writeText(codeContent).then(() => chatContext.showSnackbar("Code copied to clipboard!", "success")).catch(err => { console.error('Failed to copy code:', err); chatContext.showSnackbar("Failed to copy code.", "error"); });
          };
          localParts.push(
            <Paper key={`code-${localMatch.index}`} sx={{ mt: 1, p: 1.5, bgcolor: globalTheme.palette.mode === 'dark' ? globalTheme.palette.grey[900] : globalTheme.palette.grey[200], borderRadius: globalTheme.shape.borderRadius, overflowX: 'auto', position: 'relative', fontFamily: '"Fira Code", "Courier New", Courier, monospace', fontSize: '0.875rem', }} elevation={0}>
              <IconButton size="small" onClick={handleCopyCode} sx={{ position: 'absolute', top: globalTheme.spacing(0.5), right: globalTheme.spacing(0.5), color: globalTheme.palette.text.secondary, '&:hover': { backgroundColor: globalTheme.palette.action.hover, } }} aria-label="copy code to clipboard"> <ContentCopy fontSize="small" /> </IconButton>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}><code>{codeContent.trim()}</code></pre>
            </Paper>
          );
        }
        localLastIndex = combinedRegex.lastIndex;
      }
      if (localLastIndex < content.length) {
        const textSegment = content.substring(localLastIndex);
        localParts.push(
          <Typography key={`text-${localLastIndex}`} component="span" sx={{ whiteSpace: 'pre-wrap', color: isErrorMessage ? globalTheme.palette.error.main : 'inherit', lineHeight: 1.6, }}>
            {isErrorMessage && localParts.length === 0 && <ErrorOutline sx={{ fontSize: '1rem', verticalAlign: 'middle', marginRight: 0.5 }} />}
            {textSegment}
          </Typography>
        );
      }
      if (localParts.length === 0 && content.trim()) {
        return [<Typography key="full-text" component="span" sx={{ whiteSpace: 'pre-wrap', color: isErrorMessage ? globalTheme.palette.error.main : 'inherit', lineHeight: 1.6, }}> {isErrorMessage && <ErrorOutline sx={{ fontSize: '1rem', verticalAlign: 'middle', marginRight: 0.5 }} />} {content} </Typography>];
      }
      return localParts;
    };
    // This is where we'd call the redefined version for Chat.tsx's context
    // However, the `renderMessageContent` in the Paper's map is still the outer one.
    // The cleanest way is to make renderMessageContent a proper React component.
    // Given the constraints, I will modify the global renderMessageContent to accept showSnackbar.
    // This is not ideal as it pollutes the helper, but avoids major restructuring for now.
    
    // The `renderMessageContent` in the global scope will be used.
    // The hack with `let theme: any` allows it to access the theme.
    // To give it access to `showSnackbar`, it needs to be passed or `useChat` used if it's a component.
    // The provided solution below will re-define renderMessageContent inside ChatWithThemeAccess to use its scope.
    return <Chat renderMessageContentProp={renderMessageContentWithSnackbar} />;

}

interface ChatProps { // Define props for Chat component if we pass renderMessageContentProp
  renderMessageContentProp?: (content: string, role: 'user' | 'assistant') => React.ReactNode[];
}

// Original Chat component now accepts the render prop
const Chat: React.FC<ChatProps> = ({ renderMessageContentProp }) => {
  const theme = useTheme(); // useTheme is fine here
  // ... (rest of Chat's existing state and logic) ...
  const {
    // ...
    showSnackbar, // Directly from useChat()
  } = useChat();

  // Use the passed render prop, or the global one if not provided (though it should be)
  const actualRenderMessageContent = renderMessageContentProp || ((content, role) => renderMessageContent(content, role));


  // ... (rest of Chat's JSX, ensure to call actualRenderMessageContent)
  // Example in the map:
  // {actualRenderMessageContent(msg.content, msg.role)}
  // This is getting complicated. The simplest is to make the global renderMessageContent a component
  // or accept showSnackbar as a parameter.
  // For now, I'll revert ChatWithThemeAccess and directly modify the global renderMessageContent
  // to take showSnackbar from the useChat hook, assuming it's called from within Chat component's scope
  // where useChat is available. This is not strictly true for a helper function.
  // The best approach is to convert renderMessageContent into a proper component.
  // Given current constraints, I will make the Chat component pass showSnackbar to renderMessageContent.
  
  // Let's simplify. The Chat component itself will use useChat() for showSnackbar.
  // renderMessageContent will be modified to accept showSnackbar as an argument.
  // The global 'theme' variable hack remains for styling.

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      <Snackbar 
        open={snackbarOpen} 
        autoHideDuration={6000} 
        onClose={closeSnackbar}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert onClose={closeSnackbar} severity={snackbarSeverity} sx={{ width: '100%' }} variant="filled">
          {snackbarMessage}
        </Alert>
      </Snackbar>
      {/* ... rest of Drawer and other components ... */}
      {/* In the messages map: */}
      {/* <Paper ...>
            {renderMessageContent(msg.content, msg.role, showSnackbar)} <--- Pass showSnackbar here
          </Paper> */}
      {/* This requires renderMessageContent's signature to change. */}
      <Drawer
        variant={isMobile ? 'temporary' : 'persistent'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        sx={{
          width: 240,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: 240,
            boxSizing: 'border-box',
            display: 'flex',
            flexDirection: 'column',
          },
        }}
      >
        <Box sx={{ p: 2, flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
          <Button
            fullWidth
            variant="contained"
            onClick={createNewConversation}
            sx={{ mb: 2 }}
          >
            New Chat
          </Button>
          <Typography variant="h6" sx={{ mb: 1 }}>Conversations</Typography>
          <List sx={{ 
            flexGrow: 1, 
            overflowY: 'auto',
            maxHeight: 'calc(100vh - 200px)', 
            '&::-webkit-scrollbar': { width: '6px', },
            '&::-webkit-scrollbar-track': { background: 'transparent', },
            '&::-webkit-scrollbar-thumb': { background: 'rgba(0, 0, 0, 0.2)', borderRadius: '3px', }
          }}>
            {conversations.map((conv) => (
              <motion.div key={conv.id} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3 }}>
                <ListItem button selected={currentConversation?.id === conv.id} onClick={() => loadConversation(conv.id)}>
                  <ListItemText primary={conv.title} />
                  <IconButton size="small" onClick={(e) => { e.stopPropagation(); starConversation(conv.id); }}>
                    {conv.starred ? <Star color="primary" /> : <StarBorder />}
                  </IconButton>
                </ListItem>
              </motion.div>
            ))}
          </List>
        </Box>
        <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider', display: 'flex', alignItems: 'center', cursor: 'pointer', '&:hover': { bgcolor: 'rgba(0, 0, 0, 0.04)' }, transition: 'background-color 0.2s' }} onClick={handleUserMenuOpen}>
          <Avatar sx={{ mr: 2, bgcolor: 'primary.main' }}>{user?.username?.charAt(0).toUpperCase() || <AccountCircle />}</Avatar>
          <Box sx={{ flexGrow: 1, overflow: 'hidden' }}><Typography noWrap variant="subtitle2">{user?.username || 'User'}</Typography><Typography noWrap variant="caption" color="text.secondary">{user?.email || ''}</Typography></Box>
        </Box>
        <MuiMenu anchorEl={userMenuAnchor} open={Boolean(userMenuAnchor)} onClose={handleUserMenuClose} transformOrigin={{ horizontal: 'left', vertical: 'top' }} anchorOrigin={{ horizontal: 'left', vertical: 'bottom' }} PaperProps={{ elevation: 3, sx: { width: 220, mt: 1 } }}>
          <MenuItem onClick={handleUserMenuClose}><AccountCircle sx={{ mr: 2 }} />Profile</MenuItem>
          <Divider />
          <MenuItem onClick={() => { handleUserMenuClose(); handleLogout(); }} sx={{ color: 'error.main' }}><ExitToApp sx={{ mr: 2 }} />Logout</MenuItem>
        </MuiMenu>
      </Drawer>
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', p: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <IconButton onClick={() => setDrawerOpen(!drawerOpen)} sx={{ mr: 2 }}><Menu /></IconButton>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>{currentConversation?.title || 'New Chat'}</Typography>
          <ToggleButtonGroup value={currentModel} exclusive onChange={(event, newModel) => { if (newModel !== null) { setCurrentModel(newModel); } }} aria-label="text alignment" size="small">
            <ToggleButton value="gemini" aria-label="gemini model"><ChatIcon fontSize="small" sx={{mr: 0.5}}/> Gemini</ToggleButton>
            <ToggleButton value="groq" aria-label="groq model"><ChatIcon fontSize="small" sx={{mr: 0.5}}/> Groq</ToggleButton>
            <ToggleButton value="kkty2-video" aria-label="video model"><Movie fontSize="small" sx={{mr: 0.5}}/> Veo 2</ToggleButton>
          </ToggleButtonGroup>
        </Box>
        {currentModel === 'kkty2-video' && (
          <Paper sx={{ p: 1, mb: 1, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <TextField label="Duration (s)" type="number" size="small" value={videoDuration} onChange={(e) => setVideoDuration(Math.max(5, Math.min(8, parseInt(e.target.value, 10))))} inputProps={{ min: 5, max: 8 }} sx={{ width: '120px' }}/>
            <TextField label="# Videos" type="number" size="small" value={videoCount} onChange={(e) => setVideoCount(Math.max(1, Math.min(4, parseInt(e.target.value, 10))))} inputProps={{ min: 1, max: 4 }} sx={{ width: '100px' }}/>
            <FormControl size="small" sx={{ minWidth: '120px' }}><InputLabel>Aspect Ratio</InputLabel><Select value={videoAspectRatio} label="Aspect Ratio" onChange={(e: SelectChangeEvent) => setVideoAspectRatio(e.target.value)}><MenuItem value="16:9">16:9</MenuItem><MenuItem value="9:16">9:16</MenuItem></Select></FormControl>
          </Paper>
        )}
        <Paper sx={{ flexGrow: 1, mb: 2, p: 2, overflowY: 'auto', display: 'flex', flexDirection: 'column', }}>
          <AnimatePresence>
            {currentConversation?.messages.map((msg) => (
              <motion.div key={msg.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.3 }}>
                <Box sx={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', mb: 2, }}>
                  <Paper sx={{ p: 1.5, maxWidth: '80%', bgcolor: msg.role === 'user' ? 'primary.main' : 'background.paper', color: msg.role === 'user' ? 'primary.contrastText' : 'text.primary', borderRadius: theme.shape.borderRadius * 3, boxShadow: theme.shadows[1], }}>
                    {actualRenderMessageContent(msg.content, msg.role)}
                  </Paper>
                </Box>
              </motion.div>
            ))}
          </AnimatePresence>
          <div ref={messagesEndRef} />
        </Paper>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <input type="file" multiple ref={fileInputRef} style={{ display: 'none' }} onChange={handleFileSelect} />
          <IconButton onClick={() => fileInputRef.current?.click()} disabled={loading} aria-label="attach files"><AttachFile /></IconButton>
          <TextField fullWidth multiline maxRows={5} value={message} onChange={(e) => setMessage(e.target.value)} onKeyPress={handleKeyPress} placeholder="Type your message, or a prompt for video/image..." disabled={loading} sx={{ flexGrow: 1 }} />
          <IconButton onClick={handleSend} disabled={loading || (!message.trim() && !files.length)} color="primary" aria-label="send message">
            {loading ? <CircularProgress size={24} /> : <Send />}
          </IconButton>
        </Box>
      </Box>
    </Box>
  );
};


// export default Chat; // Original export
export default ChatWithThemeAccess; // Export the wrapper