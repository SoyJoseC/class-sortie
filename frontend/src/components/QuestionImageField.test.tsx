import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import type { Question } from '@/api/types';
import { QuestionImageField } from './QuestionImageField';
import { renderWithProviders } from '@/test/renderWithProviders';
import { stubFetch } from '@/test/mockFetch';
import { blankQuestion, validateQuestion } from '@/utils/activityDraft';

function Harness({ initial, onState }: { initial: Question; onState?: (q: Question) => void }) {
  const [question, setQuestion] = useState(initial);
  return (
    <QuestionImageField
      question={question}
      index={0}
      onChange={(next) => {
        setQuestion(next);
        onState?.(next);
      }}
    />
  );
}

function pngFile(name = 'diagram.png', type = 'image/png', size = 10) {
  return new File([new Uint8Array(size)], name, { type });
}

describe('QuestionImageField', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('uploads the chosen file and attaches the returned image id', async () => {
    const user = userEvent.setup();
    const seen: Question[] = [];
    const spy = stubFetch((url) => {
      if (url.includes('question-images')) {
        return {
          status: 201,
          body: { id: 5, url: '/media/question-images/x.png', width: 10, height: 10 },
        };
      }
      return { body: { max_image_bytes: 5 * 1024 * 1024 } };
    });
    renderWithProviders(
      <Harness initial={{ ...blankQuestion(), prompt: 'Q' }} onState={(q) => seen.push(q)} />
    );

    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    await user.upload(screen.getByLabelText(/upload a picture for question 1/i), pngFile());

    expect(await screen.findByRole('img')).toHaveAttribute(
      'src',
      '/media/question-images/x.png'
    );
    expect(seen.at(-1)?.image_id).toBe(5);
    const uploadCall = spy.mock.calls.find(([input]) =>
      String((input as { url?: string }).url ?? input).includes('question-images')
    );
    expect(uploadCall).toBeDefined();
  });

  it('refuses non-image files before uploading', async () => {
    const user = userEvent.setup({ applyAccept: false });
    const spy = stubFetch(() => ({ body: {} }));
    renderWithProviders(<Harness initial={blankQuestion()} />);

    await user.upload(
      screen.getByLabelText(/upload a picture/i),
      new File(['x'], 'notes.pdf', { type: 'application/pdf' })
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(/jpeg, png or webp/i);
    expect(
      spy.mock.calls.some(([input]) =>
        String((input as { url?: string }).url ?? input).includes('question-images')
      )
    ).toBe(false);
  });

  it('shows the server message when an upload is rejected', async () => {
    const user = userEvent.setup();
    stubFetch((url) =>
      url.includes('question-images')
        ? {
            status: 400,
            body: {
              detail: 'Invalid input.',
              code: 'validation_error',
              errors: { file: ['That file is not a readable image.'] },
            },
          }
        : { body: {} }
    );
    renderWithProviders(<Harness initial={blankQuestion()} />);

    await user.upload(screen.getByLabelText(/upload a picture/i), pngFile());

    expect(await screen.findByRole('alert')).toHaveTextContent(/not a readable image/i);
  });

  it('requires a description once a picture is attached, and can remove it', async () => {
    const user = userEvent.setup();
    const seen: Question[] = [];
    stubFetch(() => ({ body: {} }));
    const withImage: Question = {
      ...blankQuestion(),
      prompt: 'What is shown?',
      image_id: 9,
      image_url: '/media/question-images/y.png',
      image_alt: '',
    };
    renderWithProviders(<Harness initial={withImage} onState={(q) => seen.push(q)} />);

    expect(validateQuestion({ ...withImage, choices: [] })).toBe(
      'Describe the picture for students who cannot see it.'
    );

    fireEvent.change(screen.getByLabelText(/describe the picture/i), {
      target: { value: 'A switch' },
    });
    await waitFor(() => expect(seen.at(-1)?.image_alt).toBe('A switch'));

    await user.click(screen.getByRole('button', { name: /remove the picture/i }));
    expect(seen.at(-1)).toMatchObject({ image_id: null, image_url: null, image_alt: '' });
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});
