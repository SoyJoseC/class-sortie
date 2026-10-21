import { useRef, useState } from 'react';
import {
  Box,
  Button,
  FormControl,
  FormHelperText,
  FormLabel,
  HStack,
  Image,
  Input,
  Text,
  VStack,
} from '@chakra-ui/react';
import type { Question } from '@/api/types';
import { useClientConfigQuery, useUploadQuestionImageMutation } from '@/api/caricueApi';
import { errorMessage, fieldErrors } from '@/api/baseQuery';

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const DEFAULT_MAX_BYTES = 5 * 1024 * 1024;

interface QuestionImageFieldProps {
  question: Question;
  index: number;
  onChange: (question: Question) => void;
}

/**
 * Optional picture for a question (a diagram, a screenshot, a circuit).
 *
 * The file is uploaded the moment it is chosen, so the teacher sees exactly
 * what students will see; the question then carries only the resulting
 * `image_id`. Alt text is required whenever a picture is attached, so the
 * question still works for a student who cannot see it.
 */
export function QuestionImageField({ question, index, onChange }: QuestionImageFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [upload, uploadState] = useUploadQuestionImageMutation();
  const { data: config } = useClientConfigQuery();
  const [localError, setLocalError] = useState<string | null>(null);

  const maxBytes = config?.max_image_bytes ?? DEFAULT_MAX_BYTES;
  const hasImage = Boolean(question.image_id && question.image_url);
  const altId = `question-${index}-image-alt`;

  async function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ''; // allow choosing the same file again
    if (!file) return;

    setLocalError(null);
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setLocalError('Use a JPEG, PNG or WebP image.');
      return;
    }
    if (file.size > maxBytes) {
      setLocalError(
        `That image is too large (limit ${Math.floor(maxBytes / 1024 / 1024)} MB).`
      );
      return;
    }

    try {
      const uploaded = await upload(file).unwrap();
      onChange({
        ...question,
        image_id: uploaded.id,
        image_url: uploaded.url,
        image_alt: question.image_alt ?? '',
      });
    } catch (error) {
      setLocalError(
        fieldErrors(error).file ?? errorMessage(error, 'Could not upload that image.')
      );
    }
  }

  function removeImage() {
    setLocalError(null);
    onChange({ ...question, image_id: null, image_url: null, image_alt: '' });
  }

  return (
    <Box>
      <Text fontWeight="600" fontSize="sm" mb={2}>
        Picture{' '}
        <Text as="span" fontWeight="400" color="gray.600">
          (optional)
        </Text>
      </Text>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES.join(',')}
        onChange={(event) => void handleFile(event)}
        aria-label={`Upload a picture for question ${index + 1}`}
        hidden
      />

      {hasImage ? (
        <VStack align="stretch" spacing={3}>
          <Image
            src={question.image_url ?? undefined}
            alt={question.image_alt || `Picture for question ${index + 1}`}
            maxH="200px"
            objectFit="contain"
            alignSelf="flex-start"
            borderWidth="1px"
            borderColor="sand.200"
            borderRadius="md"
            bg="white"
          />
          <FormControl isRequired>
            <FormLabel htmlFor={altId} fontSize="sm">
              Describe the picture
            </FormLabel>
            <Input
              id={altId}
              value={question.image_alt ?? ''}
              onChange={(e) => onChange({ ...question, image_alt: e.target.value })}
              placeholder="Network diagram with a router joining two switches"
              maxLength={250}
            />
            <FormHelperText>
              Read aloud to students who cannot see the picture, so make it meaningful.
            </FormHelperText>
          </FormControl>
          <HStack>
            <Button
              size="sm"
              variant="outline"
              onClick={() => inputRef.current?.click()}
              isLoading={uploadState.isLoading}
            >
              Replace picture
            </Button>
            <Button
              size="sm"
              variant="ghost"
              colorScheme="coral"
              onClick={removeImage}
              aria-label={`Remove the picture from question ${index + 1}`}
            >
              Remove picture
            </Button>
          </HStack>
        </VStack>
      ) : (
        <Button
          size="sm"
          variant="outline"
          onClick={() => inputRef.current?.click()}
          isLoading={uploadState.isLoading}
          loadingText="Uploading…"
        >
          Add a picture
        </Button>
      )}

      {localError && (
        <Text role="alert" color="coral.600" fontSize="sm" mt={2}>
          {localError}
        </Text>
      )}
    </Box>
  );
}
