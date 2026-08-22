export function ErrorNotice({message, onClose}: {message: string; onClose: () => void}) {
  return (
    <div className="error-notice" role="alert">
      <span aria-hidden="true">!</span><p>{message}</p>
      <button type="button" onClick={onClose} aria-label="Dismiss error">×</button>
    </div>
  );
}

